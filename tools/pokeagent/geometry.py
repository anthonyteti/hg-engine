"""Bounded, deterministic static-terrain geometry compiler for Stage 3D.

This is deliberately not a general NSBMD writer.  It compiles a validated
rectangle/ramp terrain IR into quadrilateral Nitro display lists, PER, and the
runtime-proven HGSS BDHC subset.  Display lists are assigned only to
hash-verified shapes and material slots already present in the local template.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Any


MAP_TILES = 32
MODEL_BASE_Y = 0.25
MODEL_TILE_SCALE = 0.25
SUPPORTED_TEMPLATE_SHA256 = "f9fbf0196f416739019288f24be604fd6c096a2ec4ebf7e820e116e7ecc329cc"
MATERIAL_BINDINGS = {
    "ground": {"shape": 5, "material_index": 12, "material_name": "grass01", "capacity_bytes": 1936},
    "transition": {"shape": 6, "material_index": 17, "material_name": "road01", "capacity_bytes": 1068},
    "cliff": {"shape": 1, "material_index": 18, "material_name": "road01_r", "capacity_bytes": 2496},
}
MATERIAL_ORDER = ("ground", "transition", "cliff")


class GeometryError(ValueError):
    """Canonical terrain cannot be represented by the bounded Stage 3D subset."""

    def __init__(self, code: str, message: str, **details: object):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), **self.details}


@dataclass(frozen=True)
class Feature:
    id: str
    kind: str
    min_x: int
    max_x: int
    min_z: int
    max_z: int
    start_height: float
    end_height: float
    axis: str | None
    material: str

    def height_at(self, x: float, z: float) -> float:
        if self.axis is None:
            return self.start_height
        coordinate = x if self.axis == "x" else z
        minimum = self.min_x if self.axis == "x" else self.min_z
        maximum = self.max_x if self.axis == "x" else self.max_z
        fraction = (coordinate - minimum) / (maximum - minimum)
        return self.start_height + fraction * (self.end_height - self.start_height)

    def contains(self, x: float, z: float) -> bool:
        return self.min_x <= x < self.max_x and self.min_z <= z < self.max_z


@dataclass(frozen=True)
class Quad:
    id: str
    material: str
    vertices: tuple[tuple[float, float, float, float, float], ...]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class Triangle:
    id: str
    material: str
    vertices: tuple[tuple[float, float, float, float, float], ...]
    normal: tuple[float, float, float]


def _require_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise GeometryError("invalid_coordinate", f"{field} must be a finite number")
    return float(value)


def _parse_rectangle(value: object, feature_id: str) -> tuple[int, int, int, int]:
    if not isinstance(value, dict) or set(value) != {"min_x", "max_x", "min_z", "max_z"}:
        raise GeometryError("invalid_rectangle", f"geometry {feature_id!r} needs an exact rectangle")
    coordinates = []
    for name in ("min_x", "max_x", "min_z", "max_z"):
        number = _require_number(value[name], f"{feature_id}.{name}")
        if not number.is_integer():
            raise GeometryError("invalid_coordinate", f"{feature_id}.{name} must be an integer tile boundary")
        coordinates.append(int(number))
    min_x, max_x, min_z, max_z = coordinates
    if not (0 <= min_x < max_x <= MAP_TILES and 0 <= min_z < max_z <= MAP_TILES):
        raise GeometryError("out_of_range", f"geometry {feature_id!r} lies outside the 32x32 map")
    return min_x, max_x, min_z, max_z


def _parse_features(geometry: dict[str, Any]) -> list[Feature]:
    allowed_root = {"surfaces", "transitions", "walls", "collision"}
    if not isinstance(geometry, dict) or set(geometry) != allowed_root:
        raise GeometryError("invalid_geometry", "geometry requires surfaces, transitions, walls, and collision")
    features: list[Feature] = []
    seen: set[str] = set()
    for kind, collection in (("surface", geometry["surfaces"]), ("transition", geometry["transitions"])):
        if not isinstance(collection, list) or not collection:
            raise GeometryError("invalid_geometry", f"geometry {kind}s must be a non-empty list")
        for spec in collection:
            expected = {"id", "material", "height", "rectangle"} if kind == "surface" else {
                "id", "material", "axis", "start_height", "end_height", "rectangle",
            }
            if not isinstance(spec, dict) or set(spec) != expected:
                raise GeometryError("invalid_feature", f"{kind} contains unsupported or missing fields")
            feature_id = spec["id"]
            if not isinstance(feature_id, str) or not feature_id or feature_id in seen:
                raise GeometryError("duplicate_geometry_id", f"invalid or duplicate geometry ID {feature_id!r}")
            seen.add(feature_id)
            material = spec["material"]
            expected_material = "ground" if kind == "surface" else "transition"
            if material != expected_material:
                raise GeometryError(
                    "invalid_material", f"{kind} {feature_id!r} must use verified material {expected_material!r}",
                )
            min_x, max_x, min_z, max_z = _parse_rectangle(spec["rectangle"], feature_id)
            if kind == "surface":
                start = end = _require_number(spec["height"], f"{feature_id}.height")
                axis = None
            else:
                axis = spec["axis"]
                if axis not in ("x", "z"):
                    raise GeometryError("unsupported_transition", f"transition {feature_id!r} axis must be x or z")
                start = _require_number(spec["start_height"], f"{feature_id}.start_height")
                end = _require_number(spec["end_height"], f"{feature_id}.end_height")
                if start == end:
                    raise GeometryError("degenerate_transition", f"transition {feature_id!r} has no elevation change")
            if any(height < -8 or height > 8 for height in (start, end)):
                raise GeometryError("unsupported_height", f"geometry {feature_id!r} exceeds the bounded height range -8..8")
            features.append(Feature(feature_id, kind, min_x, max_x, min_z, max_z, start, end, axis, material))
    walls = geometry["walls"]
    collision = geometry["collision"]
    if walls != {"derive_from_height_discontinuities": True, "material": "cliff"}:
        raise GeometryError("unsupported_walls", "Stage 3D walls must be derived and use verified cliff material")
    if not isinstance(collision, dict) or set(collision) != {
        "cliff_threshold", "block_border", "permission_type", "walkable_collision", "blocked_collision",
    }:
        raise GeometryError("invalid_collision", "Stage 3D collision declaration is incomplete")
    threshold = _require_number(collision["cliff_threshold"], "collision.cliff_threshold")
    if threshold <= 0:
        raise GeometryError("invalid_collision", "cliff threshold must be positive")
    if collision["block_border"] is not True:
        raise GeometryError("invalid_collision", "Stage 3D requires a blocked perimeter")
    for name in ("permission_type", "walkable_collision", "blocked_collision"):
        value = collision[name]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255:
            raise GeometryError("invalid_collision", f"collision.{name} must be a byte")
    return features


def _tile_features(features: list[Feature]) -> list[list[Feature]]:
    grid: list[list[Feature]] = []
    for z in range(MAP_TILES):
        row = []
        for x in range(MAP_TILES):
            matches = [feature for feature in features if feature.contains(x + 0.5, z + 0.5)]
            if len(matches) != 1:
                code = "overlapping_geometry" if len(matches) > 1 else "geometry_gap"
                raise GeometryError(code, f"tile ({x}, {z}) is covered by {len(matches)} terrain features")
            row.append(matches[0])
        grid.append(row)
    return grid


def _surface_quad(feature: Feature) -> Quad:
    corners = (
        (feature.min_x, feature.min_z),
        (feature.min_x, feature.max_z),
        (feature.max_x, feature.max_z),
        (feature.max_x, feature.min_z),
    )
    vertices = tuple(
        (
            (x - 16) * MODEL_TILE_SCALE,
            MODEL_BASE_Y + feature.height_at(x, z) * MODEL_TILE_SCALE,
            (z - 16) * MODEL_TILE_SCALE,
            (x - feature.min_x) / 2,
            (z - feature.min_z) / 2,
        )
        for x, z in corners
    )
    if feature.axis == "x":
        slope_x = (feature.end_height - feature.start_height) / (feature.max_x - feature.min_x)
        normal = (-slope_x, 1.0, 0.0)
    elif feature.axis == "z":
        slope_z = (feature.end_height - feature.start_height) / (feature.max_z - feature.min_z)
        normal = (0.0, 1.0, -slope_z)
    else:
        normal = (0.0, 1.0, 0.0)
    return Quad(feature.id, feature.material, vertices, normal)


def _wall_quads(features: list[Feature], grid: list[list[Feature]], threshold: float) -> list[Quad]:
    segments: list[tuple[str, int, int, int, float, float]] = []
    # axis, fixed coordinate, interval start/end, low/high.  Heights are
    # sampled at tile centers because PER uses the same samples.
    for z in range(MAP_TILES):
        for x in range(MAP_TILES - 1):
            left, right = grid[z][x], grid[z][x + 1]
            left_h = left.height_at(x + 0.5, z + 0.5)
            right_h = right.height_at(x + 1.5, z + 0.5)
            if abs(left_h - right_h) > threshold:
                segments.append(("x", x + 1, z, z + 1, min(left_h, right_h), max(left_h, right_h)))
    for z in range(MAP_TILES - 1):
        for x in range(MAP_TILES):
            north, south = grid[z][x], grid[z + 1][x]
            north_h = north.height_at(x + 0.5, z + 0.5)
            south_h = south.height_at(x + 0.5, z + 1.5)
            if abs(north_h - south_h) > threshold:
                segments.append(("z", z + 1, x, x + 1, min(north_h, south_h), max(north_h, south_h)))

    merged: list[tuple[str, int, int, int, float, float]] = []
    for segment in sorted(segments, key=lambda item: (item[0], item[1], item[4], item[5], item[2])):
        if merged and segment[:2] == merged[-1][:2] and segment[4:] == merged[-1][4:] and segment[2] == merged[-1][3]:
            previous = merged[-1]
            merged[-1] = (previous[0], previous[1], previous[2], segment[3], previous[4], previous[5])
        else:
            merged.append(segment)

    quads = []
    for index, (axis, fixed, start, end, low, high) in enumerate(merged):
        if axis == "x":
            raw = ((fixed, low, start), (fixed, high, start), (fixed, high, end), (fixed, low, end))
            normal = (-1.0, 0.0, 0.0)
        else:
            raw = ((start, low, fixed), (end, low, fixed), (end, high, fixed), (start, high, fixed))
            normal = (0.0, 0.0, -1.0)
        vertices = tuple(
            ((x - 16) * MODEL_TILE_SCALE, MODEL_BASE_Y + y * MODEL_TILE_SCALE,
             (z - 16) * MODEL_TILE_SCALE, vertex_index % 2, (y - low) / 2)
            for vertex_index, (x, y, z) in enumerate(raw)
        )
        quads.append(Quad(f"derived_wall_{index:03d}", "cliff", vertices, normal))
    return quads


def _fx16(value: float) -> int:
    raw = round(value * 4096)
    if not -0x8000 <= raw <= 0x7FFF:
        raise GeometryError("vertex_overflow", f"vertex coordinate {value} does not fit fx16")
    return raw & 0xFFFF


def _vtx16(x: float, y: float, z: float) -> tuple[int, int]:
    return _fx16(x) | (_fx16(y) << 16), _fx16(z)


def _texcoord(s: float, t: float) -> int:
    raw_s, raw_t = round(s * 16), round(t * 16)
    if not -0x8000 <= raw_s <= 0x7FFF or not -0x8000 <= raw_t <= 0x7FFF:
        raise GeometryError("uv_overflow", "texture coordinate does not fit the Nitro s16 encoding")
    return (raw_t & 0xFFFF) << 16 | (raw_s & 0xFFFF)


def _normal(value: tuple[float, float, float]) -> int:
    length = math.sqrt(sum(component * component for component in value))
    if length == 0:
        raise GeometryError("invalid_normal", "zero-length normal")
    encoded = [round(component / length * 511) & 0x3FF for component in value]
    return encoded[0] | (encoded[1] << 10) | (encoded[2] << 20)


def _command(opcode: int, *params: int) -> bytes:
    return bytes((opcode, 0, 0, 0)) + b"".join(struct.pack("<I", value & 0xFFFFFFFF) for value in params)


def encode_quads(quads: list[Quad]) -> bytes:
    if not quads:
        raise GeometryError("empty_shape", "each selected Stage 3D shape must receive at least one quad")
    output = bytearray(_command(0x40, 1))  # BEGIN quadrilaterals
    for quad in quads:
        if len(quad.vertices) != 4:
            raise GeometryError("unsupported_primitive", f"quad {quad.id!r} does not have four vertices")
        output += _command(0x21, _normal(quad.normal))
        for x, y, z, s, t in quad.vertices:
            output += _command(0x22, _texcoord(s, t))
            output += _command(0x23, *_vtx16(x, y, z))
    output += _command(0x41)
    return bytes(output)


def encode_mesh_primitives(primitives: list[Triangle | Quad]) -> bytes:
    """Encode independent triangles/quads, grouping only consecutive source types."""
    if not primitives:
        raise GeometryError("empty_shape", "each selected asset shape must receive at least one primitive")
    output = bytearray()
    active_type: type[Triangle] | type[Quad] | None = None
    for primitive in primitives:
        primitive_type = type(primitive)
        if primitive_type not in (Triangle, Quad):
            raise GeometryError("unsupported_primitive", "asset display list accepts triangles and quads only")
        expected_vertices = 3 if primitive_type is Triangle else 4
        if len(primitive.vertices) != expected_vertices:
            raise GeometryError(
                "unsupported_primitive",
                f"{primitive.id!r} requires exactly {expected_vertices} vertices",
            )
        if active_type is not primitive_type:
            if active_type is not None:
                output += _command(0x41)
            output += _command(0x40, 0 if primitive_type is Triangle else 1)
            active_type = primitive_type
        output += _command(0x21, _normal(primitive.normal))
        for x, y, z, s, t in primitive.vertices:
            output += _command(0x22, _texcoord(s, t))
            output += _command(0x23, *_vtx16(x, y, z))
    output += _command(0x41)
    return bytes(output)


def inspect_mesh_display_list(data: bytes) -> dict[str, object]:
    """Validate and summarize the exact padded command subset emitted above."""
    offset = 0
    active: dict[str, int] | None = None
    blocks: list[dict[str, int | str]] = []
    total_vertices = 0
    while offset < len(data):
        start = offset
        if offset + 4 > len(data) or data[offset + 1:offset + 4] != b"\0\0\0":
            raise GeometryError("corrupt_display_list", "asset command is truncated or not canonically padded")
        opcode = data[offset]
        offset += 4
        parameter_words = {0x21: 1, 0x22: 1, 0x23: 2, 0x40: 1, 0x41: 0}.get(opcode)
        if parameter_words is None or offset + parameter_words * 4 > len(data):
            raise GeometryError("corrupt_display_list", f"unsupported or truncated asset opcode {opcode:#x}")
        params = data[offset:offset + parameter_words * 4]
        offset += parameter_words * 4
        if opcode == 0x40:
            if active is not None:
                raise GeometryError("corrupt_display_list", "nested BEGIN in asset display list")
            primitive_value = int.from_bytes(params, "little")
            if primitive_value not in (0, 1):
                raise GeometryError("unsupported_primitive", "asset BEGIN must select independent triangles or quads")
            active = {
                "type": primitive_value, "start": start, "vertices": 0,
                "normals": 0, "texcoords": 0,
            }
        elif opcode == 0x41:
            if active is None:
                raise GeometryError("corrupt_display_list", "END without BEGIN in asset display list")
            arity = 3 if active["type"] == 0 else 4
            if (
                active["vertices"] == 0
                or active["vertices"] % arity
                or active["texcoords"] != active["vertices"]
                or active["normals"] != active["vertices"] // arity
            ):
                raise GeometryError("corrupt_display_list", "asset primitive block has inconsistent commands")
            primitive_count = active["vertices"] // arity
            blocks.append({
                "primitive": "triangle" if active["type"] == 0 else "quad",
                "primitive_count": primitive_count,
                "vertex_count": active["vertices"],
                "bytes": offset - active["start"],
            })
            total_vertices += active["vertices"]
            active = None
        else:
            if active is None:
                raise GeometryError("corrupt_display_list", "vertex-state command occurs outside BEGIN/END")
            field = {0x21: "normals", 0x22: "texcoords", 0x23: "vertices"}[opcode]
            active[field] += 1
    if active is not None or not blocks:
        raise GeometryError("corrupt_display_list", "asset display list has an unterminated or empty primitive plan")
    return {
        "triangle_count": sum(block["primitive_count"] for block in blocks if block["primitive"] == "triangle"),
        "quad_count": sum(block["primitive_count"] for block in blocks if block["primitive"] == "quad"),
        "vertex_count": total_vertices,
        "primitive_blocks": blocks,
        "display_list_bytes": len(data),
    }


def _build_per(grid: list[list[Feature]], collision: dict[str, Any]) -> tuple[bytes, set[tuple[int, int]]]:
    blocked = {(x, z) for z in range(MAP_TILES) for x in range(MAP_TILES) if x in (0, 31) or z in (0, 31)}
    # PER has one non-directional walkability byte per tile.  As in the
    # runtime-proven Stage 3A path, interior surfaces remain PER-walkable and
    # BDHC provides height-aware ledge rejection; marking either side in PER
    # would also make valid raised-top approach tiles impassable.
    output = bytearray()
    for z in range(MAP_TILES):
        for x in range(MAP_TILES):
            value = collision["blocked_collision"] if (x, z) in blocked else collision["walkable_collision"]
            output.extend((collision["permission_type"], value))
    return bytes(output), blocked


def _build_bdhc(features: list[Feature]) -> tuple[bytes, dict[str, int]]:
    points: list[tuple[int, int]] = []
    normals: list[tuple[int, int, int]] = []
    constants: list[int] = []
    plates: list[tuple[int, int, int, int]] = []
    for feature in features:
        point_index = len(points)
        points.extend(((feature.min_x - 16, feature.min_z - 16), (feature.max_x - 16, feature.max_z - 16)))
        if feature.axis == "x":
            slope_x = (feature.end_height - feature.start_height) / (feature.max_x - feature.min_x)
            vector = (-slope_x, 1.0, 0.0)
        elif feature.axis == "z":
            slope_z = (feature.end_height - feature.start_height) / (feature.max_z - feature.min_z)
            vector = (0.0, 1.0, -slope_z)
        else:
            vector = (0.0, 1.0, 0.0)
        length = math.sqrt(sum(component * component for component in vector))
        normal = tuple(round(component / length * 4096) for component in vector)
        local_x, local_z = feature.min_x - 16, feature.min_z - 16
        constant = round(-16 * (normal[0] * local_x + normal[1] * feature.start_height + normal[2] * local_z))
        if normal not in normals:
            normals.append(normal)
        if constant not in constants:
            constants.append(constant)
        plates.append((point_index, point_index + 1, normals.index(normal), constants.index(constant)))

    boundaries = sorted({feature.max_z - 16 for feature in features})
    raw_stripes: list[tuple[int, list[int]]] = []
    previous = -16
    for boundary in boundaries:
        indices = [
            index for index, feature in enumerate(features)
            if feature.min_z - 16 < boundary and feature.max_z - 16 > previous
        ]
        if indices:
            raw_stripes.append((boundary, indices))
        previous = boundary
    # HGSS access bands include their own plates plus the immediately next
    # band's plates, then X-sort the complete candidate set.  The declarative
    # subset validates/partitions neighboring Z bands so overlapping X ranges
    # in that look-ahead set do not contradict the active band's height.
    stripes: list[tuple[int, tuple[int, ...]]] = []
    for index, (boundary, current) in enumerate(raw_stripes):
        candidates = list(current)
        if index + 1 < len(raw_stripes):
            for plate_index in raw_stripes[index + 1][1]:
                if plate_index not in candidates:
                    candidates.append(plate_index)
        candidates.sort(key=lambda plate_index: (features[plate_index].min_x, plate_index))
        stripes.append((boundary, tuple(candidates)))
    output = bytearray(b"BDHC")
    access_count = sum(len(indices) for _, indices in stripes)
    output += struct.pack("<6H", len(points), len(normals), len(constants), len(plates), len(stripes), access_count)
    for x, z in points:
        output += struct.pack("<4h", 0, x, 0, z)
    for normal in normals:
        output += struct.pack("<3i", *normal)
    for constant in constants:
        output += struct.pack("<i", constant)
    for plate in plates:
        output += struct.pack("<4H", *plate)
    access_offset = 0
    for stripe_end, indices in stripes:
        output += struct.pack("<4H", 0, stripe_end & 0xFFFF, len(indices), access_offset)
        access_offset += len(indices)
    for _, indices in stripes:
        output += struct.pack(f"<{len(indices)}H", *indices)
    return bytes(output), {
        "point_count": len(points), "normal_count": len(normals), "constant_count": len(constants),
        "plate_count": len(plates), "stripe_count": len(stripes), "access_count": access_count,
    }


def compile_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    """Validate and compile canonical Stage 3D terrain into shared artifacts."""
    features = _parse_features(geometry)
    grid = _tile_features(features)
    bdhc_features = features
    threshold = float(geometry["collision"]["cliff_threshold"])
    quads = [_surface_quad(feature) for feature in features]
    quads.extend(_wall_quads(features, grid, threshold))
    grouped = {
        material: [quad for quad in quads if quad.material == material]
        for material in MATERIAL_ORDER
    }
    display_lists = {
        MATERIAL_BINDINGS[material]["shape"]: encode_quads(material_quads)
        for material, material_quads in grouped.items()
    }
    for material in MATERIAL_ORDER:
        binding = MATERIAL_BINDINGS[material]
        encoded = display_lists[binding["shape"]]
        if len(encoded) > binding["capacity_bytes"]:
            raise GeometryError(
                "display_list_overflow",
                f"material {material!r} needs {len(encoded)} bytes but shape {binding['shape']} capacity is {binding['capacity_bytes']}",
                material=material, shape=binding["shape"], required_bytes=len(encoded),
                capacity_bytes=binding["capacity_bytes"],
            )
    per, blocked = _build_per(grid, geometry["collision"])
    bdhc, bdhc_report = _build_bdhc(bdhc_features)
    primitive_report = {
        material: {
            "shape": MATERIAL_BINDINGS[material]["shape"],
            "material_index": MATERIAL_BINDINGS[material]["material_index"],
            "material_name": MATERIAL_BINDINGS[material]["material_name"],
            "capacity_bytes": MATERIAL_BINDINGS[material]["capacity_bytes"],
            "quad_count": len(grouped[material]),
            "vertex_count": len(grouped[material]) * 4,
            "display_list_bytes": len(display_lists[MATERIAL_BINDINGS[material]["shape"]]),
        }
        for material in MATERIAL_ORDER
    }
    serializable_ir = [
        {
            "id": feature.id, "kind": feature.kind, "material": feature.material,
            "rectangle": {"min_x": feature.min_x, "max_x": feature.max_x, "min_z": feature.min_z, "max_z": feature.max_z},
            "start_height": feature.start_height, "end_height": feature.end_height, "axis": feature.axis,
        }
        for feature in features
    ]
    bdhc_ir = [
        {
            "id": feature.id,
            "rectangle": {"min_x": feature.min_x, "max_x": feature.max_x, "min_z": feature.min_z, "max_z": feature.max_z},
            "start_height": feature.start_height, "end_height": feature.end_height, "axis": feature.axis,
        }
        for feature in bdhc_features
    ]
    report = {
        "schema_version": 1,
        "primitive_type": "quads",
        "primitive_count": len(quads),
        "quad_count": len(quads),
        "triangle_count": 0,
        "vertex_count": len(quads) * 4,
        "feature_count": len(features),
        "surface_count": sum(feature.kind == "surface" for feature in features),
        "transition_count": sum(feature.kind == "transition" for feature in features),
        "derived_wall_count": len(grouped["cliff"]),
        "blocked_tile_count": len(blocked),
        "materials": primitive_report,
        "bdhc": bdhc_report,
        "hashes": {
            "per_sha256": hashlib.sha256(per).hexdigest(),
            "bdhc_sha256": hashlib.sha256(bdhc).hexdigest(),
            "display_lists": {
                str(shape): hashlib.sha256(data).hexdigest() for shape, data in sorted(display_lists.items())
            },
        },
    }
    return {
        "features": features, "bdhc_features": bdhc_features, "quads": quads,
        "ir": {"visual_features": serializable_ir, "bdhc_plates": bdhc_ir}, "display_lists": display_lists,
        "per": per, "bdhc": bdhc, "report": report,
    }
