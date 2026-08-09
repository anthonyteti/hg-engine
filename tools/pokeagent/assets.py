"""Deterministic, bounded external static-mesh ingestion.

OBJ and GLB parsers terminate at one source-neutral mesh record. Shared
normalization, validation, budgets, typed mesh IR, Nitro encoding, texture
binding, placement, and collision remain format-independent.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .asset_source import MeshCorner, MeshFace, SourceMesh
from .glb import GLBError, parse_glb
from .glb_materials import MaterialSynthesisError, synthesize_named_material
from .glb_normals import NormalGenerationError, generate_missing_normals
from .glb_preprocess import GLBPreprocessError, preprocess_static_glb
from .glb_uvs import UVGenerationError, generate_missing_uvs
from .geometry import (
    MODEL_BASE_Y,
    MODEL_TILE_SCALE,
    GeometryError,
    Quad,
    Triangle,
    encode_mesh_primitives,
    inspect_mesh_display_list,
)
from .mesh_simplify import SimplificationError, simplify_coplanar_ir
from .mesh_decimate import DecimationError, simplify_approximate_ir
from .nsbmd_model import PROJECT_DISPLAY_LIST_TESTED_MAX
from .textures import (
    compile_png,
    compile_texture_catalog,
    compile_texture_outputs,
    validate_texture_spec,
)


ASSET_SCHEMA_VERSIONS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
CATALOG_SCHEMA_VERSION = 1
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
STAGE4B_BUDGET = {
    "max_source_bytes": 262_144,
    "max_vertices": 64,
    "max_uvs": 64,
    "max_normals": 32,
    "max_faces": 24,
    "max_materials": 1,
    "max_dimension_tiles": 8.0,
    "max_height_tiles": 8.0,
    "max_collision_tiles": 64,
}
STAGE4G_SOURCE_BUDGET = {
    **STAGE4B_BUDGET,
    "max_vertices": 128,
    "max_uvs": 128,
    "max_normals": 64,
    "max_faces": 64,
}
STAGE4J_SOURCE_BUDGET = {
    **STAGE4B_BUDGET,
    "max_source_bytes": 524_288,
    "max_vertices": 512,
    "max_uvs": 512,
    "max_normals": 256,
    "max_faces": 256,
    "max_projected_source_bytes": 24_000,
}
STAGE4M_SOURCE_BUDGET = {
    **STAGE4B_BUDGET,
    "max_vertices": 256,
    "max_uvs": 256,
    "max_normals": 256,
    "max_faces": 80,
}
ASSET_MATERIAL_BINDINGS = {
    "prop": {
        "shape": 1,
        "material_index": 18,
        "material_name": "road01_r",
        "capacity_bytes": 2496,
    },
    "prop_secondary": {
        "shape": 6,
        "material_index": 17,
        "material_name": "road01",
        "capacity_bytes": 1068,
    },
}


class AssetError(ValueError):
    """An asset source, manifest, placement, or budget is unsupported."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _finite(token: str, *, field: str) -> float:
    try:
        value = float(token)
    except ValueError as error:
        raise AssetError("malformed_mesh", f"{field} is not numeric") from error
    if not math.isfinite(value):
        raise AssetError("nonfinite_coordinate", f"{field} must be finite")
    return value


def _safe_relative(root: Path, value: object, required_parent: Path, code: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AssetError(code, "asset path must be a non-empty repository-relative string")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise AssetError("unsafe_path", f"asset path escapes its canonical source root: {value}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to((root / required_parent).resolve())
    except ValueError as error:
        raise AssetError("unsafe_path", f"asset path is outside {required_parent}: {value}") from error
    return resolved


def parse_obj(data: bytes) -> SourceMesh:
    """Parse the deterministic explicit triangle/quad OBJ subset."""
    if len(data) > STAGE4B_BUDGET["max_source_bytes"]:
        raise AssetError("source_too_large", "OBJ exceeds the Stage 4B source byte budget")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AssetError("malformed_mesh", "OBJ must be UTF-8 text") from error
    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    normals: list[tuple[float, float, float]] = []
    faces: list[MeshFace] = []
    material: str | None = None
    allowed_ignored = {"o", "g", "s"}
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        keyword = fields[0]
        if keyword == "v":
            if len(fields) != 4:
                raise AssetError("malformed_mesh", f"line {line_number}: vertex requires three coordinates")
            vertices.append(tuple(_finite(value, field=f"line {line_number} vertex") for value in fields[1:]))
        elif keyword == "vt":
            if len(fields) != 3:
                raise AssetError("malformed_mesh", f"line {line_number}: UV requires two coordinates")
            uv = tuple(_finite(value, field=f"line {line_number} UV") for value in fields[1:])
            if any(value < 0.0 or value > 1.0 for value in uv):
                raise AssetError("invalid_uv", f"line {line_number}: Stage 4B UVs must be in 0..1")
            uvs.append(uv)
        elif keyword == "vn":
            if len(fields) != 4:
                raise AssetError("malformed_mesh", f"line {line_number}: normal requires three coordinates")
            normal = tuple(_finite(value, field=f"line {line_number} normal") for value in fields[1:])
            if math.sqrt(sum(value * value for value in normal)) <= 1e-9:
                raise AssetError("invalid_normal", f"line {line_number}: normal must be nonzero")
            normals.append(normal)
        elif keyword == "usemtl":
            if len(fields) != 2 or not SAFE_ID.fullmatch(fields[1]):
                raise AssetError("unsupported_material", f"line {line_number}: material name is unsupported")
            material = fields[1]
        elif keyword == "f":
            if len(fields) not in (4, 5):
                raise AssetError(
                    "unsupported_polygon", f"line {line_number}: only triangle and quad faces are supported",
                )
            if material is None:
                raise AssetError("unsupported_material", f"line {line_number}: face has no usemtl assignment")
            corners: list[MeshCorner] = []
            for token in fields[1:]:
                indices = token.split("/")
                if len(indices) != 3 or not all(indices):
                    raise AssetError("missing_uv_or_normal", f"line {line_number}: face corners require v/vt/vn")
                try:
                    vertex, uv, normal = (int(index) for index in indices)
                except ValueError as error:
                    raise AssetError("malformed_mesh", f"line {line_number}: invalid face index") from error
                if min(vertex, uv, normal) <= 0:
                    raise AssetError("unsupported_index", f"line {line_number}: zero/negative OBJ indices are unsupported")
                corners.append(MeshCorner(vertex - 1, uv - 1, normal - 1))
            faces.append(MeshFace(f"face_{len(faces):03d}", material, tuple(corners)))
        elif keyword in allowed_ignored:
            continue
        else:
            raise AssetError("unsupported_obj_statement", f"line {line_number}: unsupported OBJ statement {keyword!r}")
    if not vertices or not faces:
        raise AssetError("malformed_mesh", "OBJ must contain vertices and faces")
    for face in faces:
        for corner in face.corners:
            if corner.vertex >= len(vertices) or corner.uv >= len(uvs) or corner.normal >= len(normals):
                raise AssetError("invalid_index", f"{face.id} references an out-of-range OBJ index")
    return SourceMesh(
        tuple(vertices), tuple(uvs), tuple(normals), tuple(faces),
        {
            "source_format": "obj", "uv_origin": "lower_left",
            "scene_count": 1, "node_count": 1, "mesh_count": 1,
            "primitive_count": len(faces),
        },
    )


def _axis(value: object, field: str) -> tuple[float, float, float]:
    axes = {
        "+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0),
        "+y": (0.0, 1.0, 0.0), "-y": (0.0, -1.0, 0.0),
        "+z": (0.0, 0.0, 1.0), "-z": (0.0, 0.0, -1.0),
    }
    if value not in axes:
        raise AssetError("invalid_axis", f"{field} must be a signed X, Y, or Z axis")
    return axes[value]


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _subtract(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _normalize(vector: tuple[float, float, float], code: str) -> tuple[float, float, float]:
    length = math.sqrt(_dot(vector, vector))
    if length <= 1e-9:
        raise AssetError(code, "vector has zero length")
    return tuple(value / length for value in vector)


def _bounds(vertices: tuple[tuple[float, float, float], ...]) -> dict[str, list[float]]:
    return {
        "min": [min(vertex[axis] for vertex in vertices) for axis in range(3)],
        "max": [max(vertex[axis] for vertex in vertices) for axis in range(3)],
    }


def _validate_manifest(data: object, root: Path) -> dict[str, Any]:
    common = {
        "schema_version", "id", "source", "source_format", "category", "provenance",
        "coordinate_system", "normalization", "material_policy", "collision", "budget", "status",
    }
    if not isinstance(data, dict) or data.get("schema_version") not in ASSET_SCHEMA_VERSIONS:
        raise AssetError("unsupported_manifest_schema", "asset manifest schema_version must be in 1..12")
    expected = common | ({"textures"} if data["schema_version"] == 2 else set())
    if data["schema_version"] in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        expected |= {"texture_catalog"}
    if data["schema_version"] == 6:
        expected |= {"simplification"}
    if data["schema_version"] == 7:
        expected |= {"geometry_storage"}
    if data["schema_version"] == 8:
        expected |= {"simplification", "geometry_storage"}
    if data["schema_version"] in (9, 10, 11, 12):
        expected |= {"preprocessing"}
    if set(data) != expected:
        raise AssetError("invalid_manifest", "asset manifest has unsupported or missing fields")
    if not isinstance(data.get("id"), str) or not SAFE_ID.fullmatch(data["id"]):
        raise AssetError("invalid_asset_id", "asset id must be stable lower snake_case")
    source = _safe_relative(root, data.get("source"), Path("assets/source"), "invalid_source")
    expected_source = "glb" if data["schema_version"] in (5, 7, 8, 9, 10, 11, 12) else "obj"
    if data["schema_version"] == 6:
        expected_source = data.get("source_format")
    if expected_source not in {"obj", "glb"} or source.suffix.lower() != f".{expected_source}":
        expected_label = expected_source.upper() if isinstance(expected_source, str) else "OBJ or GLB"
        raise AssetError(
            "unsupported_source_format",
            f"asset manifest schema {data['schema_version']} requires {expected_label} source",
        )
    if not source.is_file():
        raise AssetError("missing_source", f"asset source does not exist: {data.get('source')}")
    if data.get("category") not in {"building_shell", "outdoor_prop"}:
        raise AssetError("invalid_category", "Stage 4B supports a building shell or outdoor prop")
    if data.get("status") != "proof":
        raise AssetError("invalid_status", "Stage 4B assets must retain proof status")
    provenance = data.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {"kind", "license"}:
        raise AssetError("invalid_provenance", "asset provenance must name kind and license")
    if provenance["kind"] != "project_authored" or provenance["license"] not in {"CC0-1.0", "MIT"}:
        raise AssetError("unsafe_provenance", "Stage 4B source must be explicitly project-authored and redistributable")
    coordinates = data.get("coordinate_system")
    if not isinstance(coordinates, dict) or set(coordinates) != {"units", "up_axis", "forward_axis", "handedness"}:
        raise AssetError("invalid_coordinate_system", "coordinate_system declaration is incomplete")
    if coordinates["units"] not in {"meters", "tiles"} or coordinates["handedness"] != "right":
        raise AssetError("invalid_coordinate_system", "only explicit right-handed meter/tile sources are supported")
    up = _axis(coordinates["up_axis"], "up_axis")
    forward = _axis(coordinates["forward_axis"], "forward_axis")
    if abs(_dot(up, forward)) > 1e-9:
        raise AssetError("invalid_axis", "up and forward axes must be perpendicular")
    normalization = data.get("normalization")
    if not isinstance(normalization, dict) or set(normalization) != {"scale_policy", "units_to_tiles", "anchor"}:
        raise AssetError("invalid_normalization", "normalization declaration is incomplete")
    scale = normalization["units_to_tiles"]
    if normalization["scale_policy"] != "units_to_tiles" or normalization["anchor"] != "footprint_center_base":
        raise AssetError("invalid_normalization", "Stage 4B requires units_to_tiles and footprint_center_base")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or not 0 < scale <= 16:
        raise AssetError("invalid_scale", "units_to_tiles must be finite and in (0, 16]")
    material = data.get("material_policy")
    expected_modes = {
        1: "existing_template_alias",
        2: "existing_template_alias_with_project_texture",
        3: "project_texture_catalog_binding",
        4: "project_texture_catalog_binding",
        5: "project_texture_catalog_binding",
        6: "project_texture_catalog_binding",
        7: "project_texture_catalog_binding",
        8: "project_texture_catalog_binding",
        9: "project_texture_catalog_binding",
        10: "project_texture_catalog_binding",
        11: "project_texture_catalog_binding",
        12: "project_texture_catalog_binding",
    }
    expected_mode = expected_modes[data["schema_version"]]
    if not isinstance(material, dict) or set(material) != {"mode", "mappings"} or material["mode"] != expected_mode:
        raise AssetError("unsupported_material", "asset requires an explicit bounded template material policy")
    mappings = material["mappings"]
    if not isinstance(mappings, dict) or not mappings:
        raise AssetError("unsupported_material", "Stage 4B permits exactly one mapped source material")
    if len(mappings) > STAGE4B_BUDGET["max_materials"]:
        code = "material_slot_conflict" if data["schema_version"] == 2 else "unsupported_material"
        raise AssetError(code, "the bounded asset path has exactly one verified material slot")
    if data["schema_version"] == 1:
        if any(not SAFE_ID.fullmatch(key) or value not in ASSET_MATERIAL_BINDINGS for key, value in mappings.items()):
            raise AssetError("unsupported_material", "asset material mapping names an unsupported source or template alias")
    elif data["schema_version"] == 2:
        textures = data.get("textures")
        if not isinstance(textures, list) or not textures:
            raise AssetError("invalid_texture_spec", "Stage 4C requires exactly one project texture")
        declared_texture_ids = [
            texture.get("id") for texture in textures if isinstance(texture, dict)
        ]
        if len(declared_texture_ids) != len(textures):
            raise AssetError("invalid_texture_spec", "Stage 4C texture declarations must be objects")
        if len(set(declared_texture_ids)) != len(declared_texture_ids):
            raise AssetError("duplicate_texture_id", "project-local texture IDs must be unique")
        if len(textures) != 1:
            raise AssetError("texture_slot_conflict", "Stage 4C has exactly one verified texture/palette slot")
        try:
            texture = validate_texture_spec(textures[0], root)
        except ValueError as error:
            raise AssetError(getattr(error, "code", "invalid_texture_spec"), str(error)) from error
        texture_ids = {texture["id"]}
        for source_material, mapping in mappings.items():
            if not SAFE_ID.fullmatch(source_material) or not isinstance(mapping, dict) or set(mapping) != {"alias", "texture"}:
                raise AssetError("invalid_material_texture_mapping", "Stage 4C material mapping requires alias and texture")
            if mapping["alias"] not in ASSET_MATERIAL_BINDINGS or mapping["texture"] not in texture_ids:
                raise AssetError("invalid_material_texture_mapping", "material mapping references an unsupported alias or texture")
    else:
        catalog_path = _safe_relative(
            root, data.get("texture_catalog"), Path("assets"), "invalid_texture_catalog",
        )
        if not catalog_path.is_file():
            raise AssetError("invalid_texture_catalog", "Stage 4D texture catalog does not exist")
        try:
            catalog = compile_texture_catalog(catalog_path, root)
        except ValueError as error:
            raise AssetError(getattr(error, "code", "invalid_texture_catalog"), str(error)) from error
        texture_ids = set(catalog["textures"])
        for source_material, mapping in mappings.items():
            if (
                not SAFE_ID.fullmatch(source_material)
                or not isinstance(mapping, dict)
                or set(mapping) != {"alias", "texture"}
            ):
                raise AssetError(
                    "invalid_material_texture_mapping",
                    "Stage 4D material mapping requires alias and catalog texture symbol",
                )
            if mapping["alias"] not in ASSET_MATERIAL_BINDINGS or mapping["texture"] not in texture_ids:
                raise AssetError(
                    "invalid_material_texture_mapping",
                    "material mapping references an unsupported alias or catalog texture",
                )
    collision = data.get("collision")
    if not isinstance(collision, dict) or set(collision) != {"policy", "rectangle"} or collision["policy"] != "footprint_rect":
        raise AssetError("invalid_collision_proxy", "Stage 4B requires one footprint_rect collision proxy")
    rectangle = collision["rectangle"]
    if not isinstance(rectangle, dict) or set(rectangle) != {"min_x", "max_x", "min_z", "max_z"}:
        raise AssetError("invalid_collision_proxy", "collision rectangle is incomplete")
    values = []
    for field in ("min_x", "max_x", "min_z", "max_z"):
        value = rectangle[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AssetError("invalid_collision_proxy", f"collision.{field} must be finite")
        values.append(float(value))
    if not values[0] < values[1] or not values[2] < values[3]:
        raise AssetError("invalid_collision_proxy", "collision rectangle must have nonzero dimensions")
    expected_budget = {
        6: "stage4g_dense_source",
        7: "stage4i_project_relocated",
        8: "stage4j_approximate_source",
        9: "stage4k_hierarchy_source",
        10: "stage4l_normal_source",
        11: "stage4m_uv_source",
        12: "stage4n_material_source",
    }.get(data["schema_version"], "stage4b_proof")
    if data.get("budget") != expected_budget:
        raise AssetError(
            "unsupported_budget", f"asset manifest schema {data['schema_version']} requires {expected_budget} budget",
        )
    if data["schema_version"] == 6:
        simplification = data.get("simplification")
        expected_simplification = {
            "policy", "target", "reduction_mode", "reserve_bytes",
            "preserve_boundaries", "preserve_uv_seams", "preserve_material_boundaries",
            "preserve_hard_normals",
        }
        if not isinstance(simplification, dict) or set(simplification) != expected_simplification:
            raise AssetError("invalid_simplification_policy", "Stage 4G simplification policy is incomplete")
        if (
            simplification["policy"] != "exact_coplanar_patches"
            or simplification["target"] != "fit_shape"
            or simplification["reduction_mode"] != "maximal_exact"
            or any(simplification[field] is not True for field in (
                "preserve_boundaries", "preserve_uv_seams", "preserve_material_boundaries",
                "preserve_hard_normals",
            ))
        ):
            raise AssetError(
                "unsupported_simplification_policy",
                "Stage 4G supports only maximal exact coplanar reduction with all boundaries protected",
            )
        reserve = simplification["reserve_bytes"]
        if isinstance(reserve, bool) or not isinstance(reserve, int) or not 0 <= reserve <= 2048:
            raise AssetError("invalid_target_budget", "simplification reserve_bytes must be an integer in 0..2048")
    if data["schema_version"] == 8:
        simplification = data.get("simplification")
        if not isinstance(simplification, dict) or set(simplification) != {"pipeline", "exact", "approximate"}:
            raise AssetError("invalid_approximate_simplification_policy", "Stage 4J requires exact and approximate policies")
        if simplification["pipeline"] != "exact_then_approximate":
            raise AssetError("unsupported_simplification_policy", "Stage 4J requires the exact-then-approximate pipeline")
        exact = simplification["exact"]
        if exact != {"policy": "exact_coplanar_patches", "enabled": True}:
            raise AssetError("unsupported_simplification_policy", "Stage 4J always runs the bounded exact pass first")
        approximate = simplification["approximate"]
        expected_approximate = {
            "policy", "target", "max_geometric_error", "max_surface_area_delta_percent",
            "max_bounds_delta", "min_silhouette_iou", "max_normal_deviation_degrees", "max_uv_distortion_percent",
            "hard_normal_degrees", "preserve_boundaries", "preserve_uv_seams",
            "preserve_material_boundaries", "preserve_hard_normals",
        }
        if not isinstance(approximate, dict) or set(approximate) != expected_approximate:
            raise AssetError("invalid_approximate_simplification_policy", "Stage 4J approximate policy is incomplete")
        if approximate["policy"] != "constrained_deterministic_qem" or approximate["target"] != "fit_project_geometry":
            raise AssetError("unsupported_simplification_policy", "Stage 4J supports only the constrained deterministic QEM policy")
        if any(approximate[field] is not True for field in (
            "preserve_boundaries", "preserve_uv_seams", "preserve_material_boundaries", "preserve_hard_normals",
        )):
            raise AssetError("unsupported_simplification_policy", "Stage 4J requires all structural protections")
        ranges = {
            "max_geometric_error": (0.001, 1.0), "max_bounds_delta": (0.001, 1.0),
            "max_surface_area_delta_percent": (0.1, 30.0),
            "min_silhouette_iou": (0.5, 1.0), "max_normal_deviation_degrees": (1.0, 90.0),
            "max_uv_distortion_percent": (1.0, 100.0), "hard_normal_degrees": (1.0, 120.0),
        }
        for field, (minimum, maximum) in ranges.items():
            value = approximate[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
                raise AssetError("invalid_approximate_simplification_policy", f"{field} is outside its bounded range")
    if data["schema_version"] in (7, 8):
        storage = data.get("geometry_storage")
        if not isinstance(storage, dict) or set(storage) != {"policy", "max_bytes"}:
            raise AssetError("invalid_geometry_storage", "Stage 4I geometry_storage requires policy and max_bytes")
        if storage["policy"] != "project_relocated_display_list":
            raise AssetError("unsupported_geometry_storage", "Stage 4I supports only project display-list relocation")
        maximum = storage["max_bytes"]
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= PROJECT_DISPLAY_LIST_TESTED_MAX:
            raise AssetError(
                "invalid_project_geometry_capacity",
                f"Stage 4I max_bytes must be in 1..{PROJECT_DISPLAY_LIST_TESTED_MAX}",
            )
    if data["schema_version"] == 9:
        preprocessing = data.get("preprocessing")
        if preprocessing != {
            "structure": {"policy": "flatten_static_hierarchy", "bake_transforms": True},
        }:
            raise AssetError(
                "unsupported_preprocessing_policy",
                "Stage 4K requires explicit bounded static hierarchy flattening with transform baking",
            )
    if data["schema_version"] == 10:
        preprocessing = data.get("preprocessing")
        if preprocessing != {
            "normals": {
                "policy": "crease_aware", "crease_angle_degrees": 60,
                "weighting": "area", "preserve_uv_seams": True,
                "preserve_boundaries": True,
            },
        }:
            raise AssetError(
                "unsupported_normal_generation_policy",
                "Stage 4L requires the declared 60-degree area-weighted crease-aware normal policy",
            )
    if data["schema_version"] == 11:
        preprocessing = data.get("preprocessing")
        if preprocessing != {
            "uvs": {
                "policy": "repeat_per_planar_patch", "patch_normal_degrees": 0.1,
                "plane_epsilon": 0.00001, "texture_size": 32, "padding_texels": 1,
                "preserve_aspect_ratio": True, "allow_overlapping_patches": True,
            },
        }:
            raise AssetError(
                "unsupported_uv_generation_policy",
                "Stage 4M requires the declared planar-patch 32x32 one-texel UV policy",
            )
    if data["schema_version"] == 12:
        preprocessing = data.get("preprocessing")
        declared = preprocessing.get("material") if isinstance(preprocessing, dict) else None
        if (
            not isinstance(preprocessing, dict) or set(preprocessing) != {"material"}
            or not isinstance(declared, dict) or set(declared) != {"policy", "name"}
            or declared.get("policy") != "assign_single_named_material"
            or not isinstance(declared.get("name"), str) or not SAFE_ID.fullmatch(declared["name"])
            or set(mappings) != {declared["name"]}
        ):
            raise AssetError(
                "unsupported_material_synthesis_policy",
                "Stage 4N requires one matching manifest-declared lower-snake-case source identity",
            )
    return json.loads(json.dumps(data, sort_keys=True))


def load_manifest(path: Path, root: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssetError("manifest_read_failed", f"cannot read asset manifest {path}: {error}") from error
    return _validate_manifest(data, root), raw


def _normalized_ir(manifest: dict[str, Any], mesh: SourceMesh, root: Path | None = None) -> dict[str, Any]:
    budget = (
        STAGE4J_SOURCE_BUDGET if manifest["schema_version"] == 8
        else STAGE4G_SOURCE_BUDGET if manifest["schema_version"] in (6, 7)
        else STAGE4M_SOURCE_BUDGET if manifest["schema_version"] == 11
        else STAGE4B_BUDGET
    )
    counts = {
        "vertices": len(mesh.vertices), "uvs": len(mesh.uvs),
        "normals": len(mesh.normals), "faces": len(mesh.faces),
    }
    for key, maximum in (
        ("vertices", budget["max_vertices"]),
        ("uvs", budget["max_uvs"]),
        ("normals", budget["max_normals"]),
        ("faces", budget["max_faces"]),
    ):
        if counts[key] > maximum:
            raise AssetError(f"{key}_over_budget", f"asset {key} count {counts[key]} exceeds {maximum}")
    coordinates = manifest["coordinate_system"]
    up = _axis(coordinates["up_axis"], "up_axis")
    forward = _axis(coordinates["forward_axis"], "forward_axis")
    right = _cross(up, forward)
    scale = float(manifest["normalization"]["units_to_tiles"])

    oriented = tuple(
        (_dot(vertex, right) * scale, _dot(vertex, up) * scale, _dot(vertex, forward) * scale)
        for vertex in mesh.vertices
    )
    source_bounds = _bounds(oriented)
    center_x = (source_bounds["min"][0] + source_bounds["max"][0]) / 2
    center_z = (source_bounds["min"][2] + source_bounds["max"][2]) / 2
    base_y = source_bounds["min"][1]
    vertices = tuple((x - center_x, y - base_y, z - center_z) for x, y, z in oriented)
    bounds = _bounds(vertices)
    dimensions = [bounds["max"][i] - bounds["min"][i] for i in range(3)]
    if any(dimension <= 1e-9 for dimension in dimensions):
        raise AssetError("zero_dimension", "normalized asset must have nonzero X, Y, and Z dimensions")
    if dimensions[1] > STAGE4B_BUDGET["max_height_tiles"] or any(
        dimension > STAGE4B_BUDGET["max_dimension_tiles"] for dimension in (dimensions[0], dimensions[2])
    ):
        raise AssetError("bounds_over_budget", "normalized asset exceeds the conservative Stage 4B bounds")

    material_mappings = manifest["material_policy"]["mappings"]
    texture_dimensions = {
        texture["id"]: texture["dimensions"] for texture in manifest.get("textures", [])
    }
    if manifest["schema_version"] in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        if root is None:
            raise AssetError("invalid_texture_catalog", "Stage 4D normalization requires its repository root")
        catalog = compile_texture_catalog(root / manifest["texture_catalog"], root)
        texture_dimensions = {
            symbol: texture["spec"]["dimensions"] for symbol, texture in catalog["textures"].items()
        }
    canonical_uvs = tuple(
        (u, 1.0 - v) if mesh.metadata.get("uv_origin") == "upper_left" else (u, v)
        for u, v in mesh.uvs
    )
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for uv in canonical_uvs for value in uv):
        raise AssetError("invalid_uv", "source UVs must resolve to the canonical 0..1 range")
    faces: list[dict[str, Any]] = []
    for face in mesh.faces:
        if manifest["schema_version"] < 4 and face.primitive != "quad":
            raise AssetError("unsupported_polygon", "legacy asset manifests remain quad-only")
        if face.material not in material_mappings:
            raise AssetError("unsupported_material", f"source material {face.material!r} is not mapped by the manifest")
        points = tuple(vertices[corner.vertex] for corner in face.corners)
        if len(set(points)) != len(points):
            raise AssetError("degenerate_face", f"{face.id} repeats one or more positions")
        edge_a, edge_b = _subtract(points[1], points[0]), _subtract(points[2], points[0])
        cross = _cross(edge_a, edge_b)
        normal = _normalize(cross, "degenerate_face")
        if face.primitive == "quad" and abs(_dot(_subtract(points[3], points[0]), normal)) > 1e-5:
            raise AssetError("nonplanar_face", f"{face.id} is not planar")
        oriented_normals = []
        for corner in face.corners:
            source_normal = mesh.normals[corner.normal]
            oriented_normal = _normalize(
                (_dot(source_normal, right), _dot(source_normal, up), _dot(source_normal, forward)),
                "invalid_normal",
            )
            oriented_normals.append(oriented_normal)
            if _dot(oriented_normal, normal) < 0.5:
                raise AssetError("normal_winding_mismatch", f"{face.id} normal disagrees with face winding")
        mapping = material_mappings[face.material]
        alias = mapping if isinstance(mapping, str) else mapping["alias"]
        texture_id = None if isinstance(mapping, str) else mapping["texture"]
        face_ir = {
            "id": face.id,
            "vertices": [corner.vertex for corner in face.corners],
            "uvs": [corner.uv for corner in face.corners],
            "normal": list(normal),
            "source_material": face.material,
            "material_alias": alias,
        }
        if manifest["schema_version"] >= 4:
            face_ir["primitive"] = face.primitive
        if manifest["schema_version"] == 6:
            if any(_dot(oriented_normals[0], candidate) < 1.0 - 1e-6 for candidate in oriented_normals[1:]):
                raise AssetError(
                    "simplification_normal_boundary",
                    "Stage 4G exact patches require one authored hard normal per source face",
                )
            face_ir["protected_normal"] = list(oriented_normals[0])
        if texture_id is not None:
            face_ir["texture"] = texture_id
        faces.append(face_ir)

    source_materials = sorted({face.material for face in mesh.faces})
    if len(source_materials) > STAGE4B_BUDGET["max_materials"]:
        raise AssetError("material_over_budget", "asset uses too many source materials")
    ir = {
        "schema_version": 2 if manifest["schema_version"] >= 4 else 1,
        "asset_id": manifest["id"],
        "coordinate_convention": {
            "units": "map_tiles", "up_axis": "+y", "forward_axis": "+z",
            "handedness": "right", "anchor": "footprint_center_base",
        },
        "vertices": [list(vertex) for vertex in vertices],
        "uvs": [list(uv) for uv in canonical_uvs],
        "faces": faces,
        "bounds": bounds,
        "source_bounds_after_axis_scale": source_bounds,
        "dimensions": dimensions,
        "materials": source_materials,
    }
    if texture_dimensions:
        ir["texture_dimensions"] = texture_dimensions
    return ir


def _ir_primitives(ir: dict[str, Any], placement: dict[str, Any] | None = None) -> list[Triangle | Quad]:
    rotation = int((placement or {}).get("rotation", 0))
    anchor_x = float((placement or {}).get("x", 16))
    anchor_z = float((placement or {}).get("z", 16))

    def transform(position: list[float]) -> tuple[float, float, float]:
        x, y, z = position
        if rotation == 0:
            rx, rz = x, z
        elif rotation == 90:
            rx, rz = z, -x
        elif rotation == 180:
            rx, rz = -x, -z
        else:
            rx, rz = -z, x
        return (
            (anchor_x + rx - 16) * MODEL_TILE_SCALE,
            MODEL_BASE_Y + y * MODEL_TILE_SCALE,
            (anchor_z + rz - 16) * MODEL_TILE_SCALE,
        )

    primitives: list[Triangle | Quad] = []
    for face in ir["faces"]:
        points = [transform(ir["vertices"][index]) for index in face["vertices"]]
        normal = _normalize(_cross(_subtract(points[1], points[0]), _subtract(points[2], points[0])), "degenerate_face")
        if face.get("texture") is None:
            uvs = [ir["uvs"][uv_index] for uv_index in face["uvs"]]
        else:
            width, height = ir["texture_dimensions"][face["texture"]]
            # OBJ's V origin is the bottom edge; PNG/Nitro row zero is the top.
            # Nitro TEXCOORD uses 1/16 texel units, so normalized OBJ UVs are
            # converted to texel coordinates before geometry encoding.
            uvs = [
                [ir["uvs"][uv_index][0] * width, (1.0 - ir["uvs"][uv_index][1]) * height]
                for uv_index in face["uvs"]
            ]
        vertices = tuple((*point, *uv) for point, uv in zip(points, uvs, strict=True))
        prefix = (placement or {}).get("id", ir["asset_id"])
        primitive_class = Triangle if face.get("primitive", "quad") == "triangle" else Quad
        primitives.append(primitive_class(
            f"{prefix}:{face['id']}", face["material_alias"], vertices, normal,
        ))
    return primitives


def _encode_asset_primitives(primitives: list[Triangle | Quad]) -> tuple[bytes, dict[str, object]]:
    try:
        display_list = encode_mesh_primitives(primitives)
        return display_list, inspect_mesh_display_list(display_list)
    except GeometryError as error:
        raise AssetError(error.code, str(error), **error.details) from error


def compile_asset(manifest_path: Path, root: Path) -> dict[str, Any]:
    manifest, manifest_bytes = load_manifest(manifest_path, root)
    source_path = (root / manifest["source"]).resolve()
    source_bytes = source_path.read_bytes()
    preprocess_result = None
    normal_result = None
    uv_result = None
    material_result = None
    if manifest["source_format"] == "obj":
        mesh = parse_obj(source_bytes)
    else:
        try:
            parse_bytes = source_bytes
            if manifest["schema_version"] == 9:
                preprocess_result = preprocess_static_glb(source_bytes)
                parse_bytes = preprocess_result["canonical_glb"]
            elif manifest["schema_version"] == 10:
                normal_result = generate_missing_normals(source_bytes)
                parse_bytes = normal_result["canonical_glb"]
            elif manifest["schema_version"] == 11:
                uv_result = generate_missing_uvs(source_bytes)
                parse_bytes = uv_result["canonical_glb"]
            elif manifest["schema_version"] == 12:
                material_result = synthesize_named_material(
                    source_bytes, manifest["preprocessing"]["material"]["name"],
                )
                parse_bytes = material_result["canonical_glb"]
            mesh = parse_glb(
                parse_bytes,
                STAGE4J_SOURCE_BUDGET | {"max_accessor_elements": 1024, "max_buffer_bytes": 524_288}
                if manifest["schema_version"] == 8 else None,
            )
        except (GLBError, GLBPreprocessError, MaterialSynthesisError, NormalGenerationError, UVGenerationError) as error:
            raise AssetError(error.code, str(error), **error.details) from error
    source_ir = _normalized_ir(manifest, mesh, root)
    source_primitives = _ir_primitives(source_ir)
    aliases = sorted({primitive.material for primitive in source_primitives})
    if len(aliases) != 1:
        raise AssetError("unsupported_material", "asset must resolve to one verified template alias")
    binding = ASSET_MATERIAL_BINDINGS[aliases[0]]
    source_display_list, source_primitive_plan = _encode_asset_primitives(source_primitives)
    if manifest["schema_version"] == 8 and len(source_display_list) > STAGE4J_SOURCE_BUDGET["max_projected_source_bytes"]:
        raise AssetError(
            "projected_source_over_budget", "Stage 4J source exceeds the bounded preprocessing envelope",
            projected_bytes=len(source_display_list),
            maximum_bytes=STAGE4J_SOURCE_BUDGET["max_projected_source_bytes"],
        )
    ir = source_ir
    simplification_report = None
    target_bytes = binding["capacity_bytes"]
    if manifest["schema_version"] == 6:
        target_bytes -= manifest["simplification"]["reserve_bytes"]
        if target_bytes <= 0:
            raise AssetError(
                "invalid_target_budget", "simplification reserve leaves no usable shape capacity",
                capacity_bytes=binding["capacity_bytes"], reserve_bytes=manifest["simplification"]["reserve_bytes"],
            )
        try:
            ir, simplification_report = simplify_coplanar_ir(source_ir)
        except SimplificationError as error:
            raise AssetError(error.code, str(error), **error.details) from error
    elif manifest["schema_version"] == 7:
        target_bytes = manifest["geometry_storage"]["max_bytes"]
    elif manifest["schema_version"] == 8:
        target_bytes = manifest["geometry_storage"]["max_bytes"]
        try:
            exact_ir, exact_report = simplify_coplanar_ir(source_ir)
        except SimplificationError as error:
            raise AssetError(error.code, str(error), **error.details) from error
        exact_display_list, exact_plan = _encode_asset_primitives(_ir_primitives(exact_ir))
        try:
            ir, approximate_report = simplify_approximate_ir(
                exact_ir, target_bytes, manifest["simplification"]["approximate"],
            )
        except DecimationError as error:
            raise AssetError(error.code, str(error), **error.details) from error
        simplification_report = {
            "pipeline": "exact_then_approximate", "exact": exact_report,
            "approximate": approximate_report,
            "source_projected_display_list_bytes": len(source_display_list),
            "post_exact_display_list_bytes": len(exact_display_list),
            "post_exact_counts": {
                "triangles": exact_plan["triangle_count"], "quads": exact_plan["quad_count"],
                "emitted_vertices": exact_plan["vertex_count"],
            },
        }
    primitives = _ir_primitives(ir)
    display_list, primitive_plan = _encode_asset_primitives(primitives)
    if len(display_list) > target_bytes:
        code = (
            "simplification_target_unreachable" if manifest["schema_version"] in (6, 8)
            else "project_geometry_capacity_exceeded" if manifest["schema_version"] == 7
            else "display_list_overflow"
        )
        details: dict[str, object] = {
            "required_bytes": len(display_list), "target_bytes": target_bytes,
            "capacity_bytes": binding["capacity_bytes"], "shape": binding["shape"],
        }
        message = "asset display list exceeds its allowed template shape budget"
        if manifest["schema_version"] in (7, 8):
            message = "asset display list exceeds its configured geometry storage"
            details.update({
                "asset_id": manifest["id"],
                "tested_project_capacity_bytes": PROJECT_DISPLAY_LIST_TESTED_MAX,
            })
        raise AssetError(
            code, message, **details,
        )
    rectangle = {key: float(value) for key, value in manifest["collision"]["rectangle"].items()}
    bounds = ir["bounds"]
    if not (
        bounds["min"][0] <= rectangle["min_x"] < rectangle["max_x"] <= bounds["max"][0]
        and bounds["min"][2] <= rectangle["min_z"] < rectangle["max_z"] <= bounds["max"][2]
    ):
        raise AssetError("collision_bounds_mismatch", "collision footprint must remain within normalized X/Z bounds")
    report = {
        "schema_version": manifest["schema_version"],
        "success": True,
        "asset_id": manifest["id"],
        "source": manifest["source"],
        "source_format": manifest["source_format"],
        "source_sha256": _hash(source_bytes),
        "manifest_sha256": _hash(manifest_bytes),
        "source_details": mesh.metadata,
        "source_counts": {
            "vertices": len(mesh.vertices), "uvs": len(mesh.uvs),
            "normals": len(mesh.normals), "faces": len(mesh.faces),
        },
        "source_normalized_counts": {
            "vertices": len(source_ir["vertices"]), "faces": len(source_ir["faces"]),
            "quads": source_primitive_plan["quad_count"], "triangles": source_primitive_plan["triangle_count"],
            "emitted_vertices": source_primitive_plan["vertex_count"],
        },
        "normalized_counts": {
            "vertices": len(ir["vertices"]), "faces": len(ir["faces"]),
            "quads": primitive_plan["quad_count"], "triangles": primitive_plan["triangle_count"],
        },
        "emitted_vertex_count": primitive_plan["vertex_count"],
        "primitive_blocks": primitive_plan["primitive_blocks"],
        "primitive_bytes": {
            kind: sum(
                int(block["bytes"]) for block in primitive_plan["primitive_blocks"]
                if block["primitive"] == kind
            )
            for kind in ("triangle", "quad")
        },
        "source_bounds_after_axis_scale": ir["source_bounds_after_axis_scale"],
        "normalized_bounds": ir["bounds"],
        "dimensions_tiles": ir["dimensions"],
        "material_mappings": manifest["material_policy"]["mappings"],
        "shape": binding["shape"],
        "material_index": binding["material_index"],
        "material_name": binding["material_name"],
        "display_list_bytes": len(display_list),
        "display_list_capacity_bytes": target_bytes if manifest["schema_version"] in (7, 8) else binding["capacity_bytes"],
        "inherited_display_list_capacity_bytes": binding["capacity_bytes"],
        "display_list_target_bytes": target_bytes,
        "shape_utilization_percent": round(len(display_list) * 100 / target_bytes, 3),
        "collision": {"policy": "footprint_rect", "rectangle": rectangle},
        "budget": dict(
            STAGE4J_SOURCE_BUDGET if manifest["schema_version"] == 8
            else STAGE4G_SOURCE_BUDGET if manifest["schema_version"] in (6, 7)
            else STAGE4M_SOURCE_BUDGET if manifest["schema_version"] == 11
            else STAGE4B_BUDGET
        ),
        "hashes": {
            "normalized_source_mesh_sha256": _hash((json.dumps(source_ir, sort_keys=True, separators=(",", ":")) + "\n").encode()),
            "normalized_mesh_sha256": _hash((json.dumps(ir, sort_keys=True, separators=(",", ":")) + "\n").encode()),
            "display_list_sha256": _hash(display_list),
            "collision_sha256": _hash((json.dumps(rectangle, sort_keys=True, separators=(",", ":")) + "\n").encode()),
        },
    }
    if preprocess_result is not None:
        report["preprocessing"] = preprocess_result["report"]
        report["hashes"]["preprocessed_glb_sha256"] = _hash(preprocess_result["canonical_glb"])
    if normal_result is not None:
        report["normal_generation"] = normal_result["report"]
        report["hashes"]["normal_generated_glb_sha256"] = _hash(normal_result["canonical_glb"])
    if uv_result is not None:
        report["uv_generation"] = uv_result["report"]
        report["hashes"]["uv_generated_glb_sha256"] = _hash(uv_result["canonical_glb"])
    if material_result is not None:
        report["material_synthesis"] = material_result["report"]
        report["hashes"]["material_generated_glb_sha256"] = _hash(material_result["canonical_glb"])
    if simplification_report is not None and manifest["schema_version"] == 6:
        source_bytes_count = len(source_display_list)
        simplification_report.update({
            "applied": True,
            "source_projected_display_list_bytes": source_bytes_count,
            "simplified_display_list_bytes": len(display_list),
            "shape_capacity_bytes": binding["capacity_bytes"],
            "target_bytes": target_bytes,
            "source_overflow_bytes": max(0, source_bytes_count - binding["capacity_bytes"]),
            "final_utilization_percent": round(len(display_list) * 100 / binding["capacity_bytes"], 3),
            "face_reduction_percent": round(
                (len(source_ir["faces"]) - len(ir["faces"])) * 100 / len(source_ir["faces"]), 3,
            ),
            "byte_reduction_percent": round((source_bytes_count - len(display_list)) * 100 / source_bytes_count, 3),
        })
        report["simplification"] = simplification_report
    elif simplification_report is not None:
        simplification_report.update({
            "final_display_list_bytes": len(display_list), "target_bytes": target_bytes,
            "final_utilization_percent": round(len(display_list) * 100 / target_bytes, 3),
            "source_overflow_bytes": max(0, len(source_display_list) - target_bytes),
            "post_exact_overflow_bytes": max(0, simplification_report["post_exact_display_list_bytes"] - target_bytes),
        })
        report["simplification"] = simplification_report
    if manifest["schema_version"] in (7, 8):
        report["geometry_storage"] = {
            **manifest["geometry_storage"],
            "inherited_capacity_bytes": binding["capacity_bytes"],
            "tested_project_capacity_bytes": PROJECT_DISPLAY_LIST_TESTED_MAX,
            "requires_relocation": len(display_list) > binding["capacity_bytes"],
        }
    compiled_textures = {
        texture["id"]: compile_png(texture, root) for texture in manifest.get("textures", [])
    }
    if manifest["schema_version"] in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        compiled_textures = compile_texture_catalog(root / manifest["texture_catalog"], root)["textures"]
    if compiled_textures:
        report["textures"] = {
            texture_id: compiled_textures[texture_id]["report"] for texture_id in sorted(compiled_textures)
        }
    return {
        "manifest": manifest, "mesh": mesh, "source_ir": source_ir, "ir": ir, "primitives": primitives,
        "triangles": [primitive for primitive in primitives if isinstance(primitive, Triangle)],
        "quads": [primitive for primitive in primitives if isinstance(primitive, Quad)],
        "display_list": display_list, "collision": rectangle, "textures": compiled_textures, "report": report,
        "preprocessed_glb": preprocess_result["canonical_glb"] if preprocess_result is not None else None,
        "normal_generated_glb": normal_result["canonical_glb"] if normal_result is not None else None,
        "uv_generated_glb": uv_result["canonical_glb"] if uv_result is not None else None,
        "material_generated_glb": material_result["canonical_glb"] if material_result is not None else None,
    }


def compile_asset_outputs(manifest_path: Path, output: Path, root: Path) -> dict[str, Any]:
    compiled = compile_asset(manifest_path, root)
    output.mkdir(parents=True, exist_ok=True)
    source_ir_bytes = (json.dumps(compiled["source_ir"], indent=2, sort_keys=True) + "\n").encode()
    ir_bytes = (json.dumps(compiled["ir"], indent=2, sort_keys=True) + "\n").encode()
    collision_bytes = (json.dumps({
        "schema_version": 1, "asset_id": compiled["manifest"]["id"],
        "policy": "footprint_rect", "rectangle": compiled["collision"],
    }, indent=2, sort_keys=True) + "\n").encode()
    (output / "normalized-mesh.json").write_bytes(source_ir_bytes)
    if compiled["manifest"]["schema_version"] in (6, 8):
        (output / "simplified-mesh.json").write_bytes(ir_bytes)
    (output / "display-list.bin").write_bytes(compiled["display_list"])
    (output / "collision.json").write_bytes(collision_bytes)
    for texture_id, texture in sorted(compiled["textures"].items()):
        texture_output = output / "textures" / texture_id
        compile_texture_outputs(texture["spec"], texture_output, root)
    report = dict(compiled["report"])
    report["outputs"] = {
        "normalized_mesh": "normalized-mesh.json",
        "display_list": "display-list.bin",
        "collision": "collision.json",
        "report": "asset-report.json",
    }
    if compiled["preprocessed_glb"] is not None:
        (output / "preprocessed.glb").write_bytes(compiled["preprocessed_glb"])
        preprocess_report = compiled["report"]["preprocessing"]
        (output / "preprocess-report.json").write_text(
            json.dumps(preprocess_report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        report["outputs"]["preprocessed_glb"] = "preprocessed.glb"
        report["outputs"]["preprocess_report"] = "preprocess-report.json"
    if compiled["normal_generated_glb"] is not None:
        (output / "normal-generated.glb").write_bytes(compiled["normal_generated_glb"])
        (output / "normal-generation-report.json").write_text(
            json.dumps(compiled["report"]["normal_generation"], indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        report["outputs"]["normal_generated_glb"] = "normal-generated.glb"
        report["outputs"]["normal_generation_report"] = "normal-generation-report.json"
    if compiled["uv_generated_glb"] is not None:
        (output / "uv-generated.glb").write_bytes(compiled["uv_generated_glb"])
        (output / "uv-generation-report.json").write_text(
            json.dumps(compiled["report"]["uv_generation"], indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        report["outputs"]["uv_generated_glb"] = "uv-generated.glb"
        report["outputs"]["uv_generation_report"] = "uv-generation-report.json"
    if compiled["material_generated_glb"] is not None:
        (output / "material-generated.glb").write_bytes(compiled["material_generated_glb"])
        (output / "material-synthesis-report.json").write_text(
            json.dumps(compiled["report"]["material_synthesis"], indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        report["outputs"]["material_generated_glb"] = "material-generated.glb"
        report["outputs"]["material_synthesis_report"] = "material-synthesis-report.json"
    if compiled["manifest"]["schema_version"] in (6, 8):
        report["outputs"]["simplified_mesh"] = "simplified-mesh.json"
    if compiled["textures"]:
        report["outputs"]["textures"] = "textures/"
    (output / "asset-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def load_catalog(path: Path, root: Path) -> dict[str, Path]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssetError("catalog_read_failed", f"cannot read asset catalog {path}: {error}") from error
    if not isinstance(data, dict) or set(data) != {"schema_version", "assets"} or data["schema_version"] != 1:
        raise AssetError("invalid_catalog", "asset catalog must use schema_version 1 and an assets list")
    if not isinstance(data["assets"], list) or not data["assets"]:
        raise AssetError("invalid_catalog", "asset catalog must contain at least one asset")
    catalog: dict[str, Path] = {}
    for entry in data["assets"]:
        if not isinstance(entry, dict) or set(entry) != {"id", "manifest"}:
            raise AssetError("invalid_catalog", "catalog entry requires id and manifest")
        asset_id = entry["id"]
        if not isinstance(asset_id, str) or not SAFE_ID.fullmatch(asset_id) or asset_id in catalog:
            raise AssetError("duplicate_asset_id", f"invalid or duplicate catalog asset id {asset_id!r}")
        manifest_path = _safe_relative(root, entry["manifest"], Path("assets/manifests"), "invalid_manifest")
        manifest, _raw = load_manifest(manifest_path, root)
        if manifest["id"] != asset_id:
            raise AssetError("catalog_manifest_mismatch", f"catalog id {asset_id!r} disagrees with its manifest")
        catalog[asset_id] = manifest_path
    return catalog


def _rotated_rectangle(rectangle: dict[str, float], placement: dict[str, Any]) -> tuple[float, float, float, float]:
    corners = (
        (rectangle["min_x"], rectangle["min_z"]),
        (rectangle["min_x"], rectangle["max_z"]),
        (rectangle["max_x"], rectangle["min_z"]),
        (rectangle["max_x"], rectangle["max_z"]),
    )
    rotated = []
    for x, z in corners:
        rotation = placement["rotation"]
        if rotation == 0:
            rx, rz = x, z
        elif rotation == 90:
            rx, rz = z, -x
        elif rotation == 180:
            rx, rz = -x, -z
        else:
            rx, rz = -z, x
        rotated.append((placement["x"] + rx, placement["z"] + rz))
    return (
        min(value[0] for value in rotated), max(value[0] for value in rotated),
        min(value[1] for value in rotated), max(value[1] for value in rotated),
    )


def compile_placements(catalog_path: Path, placements: object, root: Path) -> dict[str, Any]:
    catalog = load_catalog(catalog_path, root)
    if not isinstance(placements, list) or not placements:
        raise AssetError("invalid_placement", "asset placements must be a non-empty list")
    seen: set[str] = set()
    primitives_by_shape: dict[int, list[Triangle | Quad]] = {}
    blocked: set[tuple[int, int]] = set()
    placement_ir: list[dict[str, Any]] = []
    asset_reports: dict[str, dict[str, Any]] = {}
    project_capacity_by_shape: dict[int, int] = {}
    asset_ids_by_shape: dict[int, set[str]] = {}
    for placement in placements:
        if not isinstance(placement, dict) or set(placement) != {"id", "asset", "x", "z", "rotation"}:
            raise AssetError("invalid_placement", "placement requires id, asset, x, z, and rotation")
        placement_id = placement["id"]
        if not isinstance(placement_id, str) or not SAFE_ID.fullmatch(placement_id) or placement_id in seen:
            raise AssetError("duplicate_placement_id", f"invalid or duplicate placement id {placement_id!r}")
        seen.add(placement_id)
        asset_id = placement["asset"]
        if asset_id not in catalog:
            raise AssetError("unknown_asset", f"placement references unknown asset {asset_id!r}")
        if any(isinstance(placement[key], bool) or not isinstance(placement[key], int) for key in ("x", "z")):
            raise AssetError("invalid_placement", "placement X/Z anchors must be integer tile coordinates")
        if placement["rotation"] not in (0, 90, 180, 270):
            raise AssetError("invalid_rotation", "placement rotation must be 0, 90, 180, or 270")
        compiled = compile_asset(catalog[asset_id], root)
        asset_reports[asset_id] = compiled["report"]
        mapping_values = compiled["manifest"]["material_policy"]["mappings"].values()
        aliases = {
            value if isinstance(value, str) else value["alias"] for value in mapping_values
        }
        binding = ASSET_MATERIAL_BINDINGS[next(iter(aliases))]
        asset_ids_by_shape.setdefault(binding["shape"], set()).add(asset_id)
        if compiled["manifest"]["schema_version"] in (7, 8):
            project_capacity = int(compiled["manifest"]["geometry_storage"]["max_bytes"])
            previous = project_capacity_by_shape.setdefault(binding["shape"], project_capacity)
            if previous != project_capacity:
                raise AssetError(
                    "project_geometry_capacity_conflict",
                    "placements sharing one shape must use one project capacity",
                    shape=binding["shape"], capacities=sorted({previous, project_capacity}),
                )
        primitives_by_shape.setdefault(binding["shape"], []).extend(_ir_primitives(compiled["ir"], placement))
        rectangle = compiled["collision"]
        min_x, max_x, min_z, max_z = _rotated_rectangle(rectangle, placement)
        visual_bounds = compiled["ir"]["bounds"]
        visual_width = visual_bounds["max"][0] - visual_bounds["min"][0]
        visual_depth = visual_bounds["max"][2] - visual_bounds["min"][2]
        if placement["rotation"] in (90, 270):
            visual_width, visual_depth = visual_depth, visual_width
        visual_min_x = placement["x"] - visual_width / 2
        visual_max_x = placement["x"] + visual_width / 2
        visual_min_z = placement["z"] - visual_depth / 2
        visual_max_z = placement["z"] + visual_depth / 2
        if not (0 <= visual_min_x < visual_max_x <= 32 and 0 <= visual_min_z < visual_max_z <= 32):
            raise AssetError("placement_out_of_bounds", f"placement {placement_id!r} visual bounds leave the map")
        if not (1 <= min_x < max_x <= 31 and 1 <= min_z < max_z <= 31):
            raise AssetError("collision_out_of_bounds", f"placement {placement_id!r} collision reaches the external border")
        placement_blocked = {
            (x, z) for z in range(32) for x in range(32)
            if min_x <= x + 0.5 < max_x and min_z <= z + 0.5 < max_z
        }
        if not placement_blocked:
            raise AssetError("empty_collision_proxy", f"placement {placement_id!r} blocks no tile centers")
        if blocked & placement_blocked:
            raise AssetError("overlapping_asset_collision", f"placement {placement_id!r} overlaps another collision proxy")
        blocked.update(placement_blocked)
        placement_ir.append({
            "id": placement_id, "asset": asset_id, "x": placement["x"], "z": placement["z"],
            "rotation": placement["rotation"],
            "visual_bounds": {"min_x": visual_min_x, "max_x": visual_max_x, "min_z": visual_min_z, "max_z": visual_max_z},
            "collision_bounds": {"min_x": min_x, "max_x": max_x, "min_z": min_z, "max_z": max_z},
            "blocked_tiles": [list(tile) for tile in sorted(placement_blocked, key=lambda item: (item[1], item[0]))],
        })
    if len(blocked) > STAGE4B_BUDGET["max_collision_tiles"]:
        raise AssetError("collision_over_budget", "placed asset collision exceeds the Stage 4B tile budget")
    display_lists: dict[int, bytes] = {}
    shape_reports: list[dict[str, Any]] = []
    for shape in sorted(primitives_by_shape):
        primitives = primitives_by_shape[shape]
        aliases = sorted({primitive.material for primitive in primitives})
        bindings = {ASSET_MATERIAL_BINDINGS[alias]["shape"]: ASSET_MATERIAL_BINDINGS[alias] for alias in aliases}
        if set(bindings) != {shape}:
            raise AssetError("material_slot_conflict", "one shape received incompatible material aliases")
        inherited_capacity = min(ASSET_MATERIAL_BINDINGS[alias]["capacity_bytes"] for alias in aliases)
        capacity = project_capacity_by_shape.get(shape, inherited_capacity)
        display_list, primitive_plan = _encode_asset_primitives(primitives)
        if len(display_list) > capacity:
            code = "project_geometry_capacity_exceeded" if shape in project_capacity_by_shape else "display_list_overflow"
            raise AssetError(
                code, "placed asset display list exceeds its configured geometry storage",
                asset_ids=sorted(asset_ids_by_shape[shape]), required_bytes=len(display_list),
                capacity_bytes=capacity, shape=shape,
            )
        display_lists[shape] = display_list
        shape_reports.append({
            "shape": shape, "aliases": aliases,
            "triangle_count": primitive_plan["triangle_count"],
            "quad_count": primitive_plan["quad_count"],
            "vertex_count": primitive_plan["vertex_count"],
            "primitive_blocks": primitive_plan["primitive_blocks"],
            "display_list_bytes": len(display_list), "capacity_bytes": capacity,
            "inherited_capacity_bytes": inherited_capacity,
            "storage_policy": (
                "project_relocated_display_list" if shape in project_capacity_by_shape else "inherited_template_region"
            ),
            "utilization_percent": round(len(display_list) * 100 / capacity, 3),
            "sha256": _hash(display_list),
        })
    ir = {"schema_version": 1, "placements": placement_ir}
    report = {
        "schema_version": 1,
        "asset_count": len(asset_reports),
        "placement_count": len(placement_ir),
        "triangle_count": sum(
            isinstance(primitive, Triangle)
            for primitives in primitives_by_shape.values() for primitive in primitives
        ),
        "quad_count": sum(
            isinstance(primitive, Quad)
            for primitives in primitives_by_shape.values() for primitive in primitives
        ),
        "vertex_count": sum(
            len(primitive.vertices)
            for primitives in primitives_by_shape.values() for primitive in primitives
        ),
        "shapes": shape_reports,
        "relocation_capacities": dict(sorted(project_capacity_by_shape.items())),
        "blocked_tile_count": len(blocked),
        "assets": {key: asset_reports[key] for key in sorted(asset_reports)},
        "hashes": {
            "placement_ir_sha256": _hash((json.dumps(ir, sort_keys=True, separators=(",", ":")) + "\n").encode()),
            "display_lists_sha256": _hash(b"".join(display_lists[shape] for shape in sorted(display_lists))),
            "collision_sha256": _hash((json.dumps(sorted(blocked), separators=(",", ":")) + "\n").encode()),
        },
    }
    return {
        "ir": ir,
        "primitives": [
            primitive for shape in sorted(primitives_by_shape) for primitive in primitives_by_shape[shape]
        ],
        "triangles": [
            primitive for shape in sorted(primitives_by_shape)
            for primitive in primitives_by_shape[shape] if isinstance(primitive, Triangle)
        ],
        "quads": [
            primitive for shape in sorted(primitives_by_shape)
            for primitive in primitives_by_shape[shape] if isinstance(primitive, Quad)
        ],
        "display_lists": display_lists,
        "triangle_counts": {
            shape: sum(isinstance(primitive, Triangle) for primitive in primitives)
            for shape, primitives in sorted(primitives_by_shape.items())
        },
        "quad_counts": {
            shape: sum(isinstance(primitive, Quad) for primitive in primitives)
            for shape, primitives in sorted(primitives_by_shape.items())
        },
        "blocked_tiles": blocked,
        "relocation_capacities": dict(sorted(project_capacity_by_shape.items())),
        "report": report,
    }
