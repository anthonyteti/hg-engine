"""Bounded deterministic PNG -> Nitro PLTT16 texture compilation.

This is deliberately not a general NSBTX writer.  It compiles one opaque
32x32 project-authored PNG to Nitro's four-bit paletted texel stream and
patches one hash-locked texture/palette payload pair inside the verified HGSS
area-data BTX0 member while preserving every dictionary and unrelated byte.

Stage 4D additionally owns a persistent project texture catalog.  It rebuilds
one appended, project-only area-texture member from hash-locked dictionary and
layout metadata: every inherited texel/palette payload byte is cleared before
the centrally allocated project entries are written.  It does not create
Nitro dictionaries or claim support for arbitrary TEX0 layouts.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any

from PIL import Image, UnidentifiedImageError


TEXTURE_SCHEMA_VERSION = 1
PROJECT_TEXTURE_SCHEMA_VERSION = 2
TEXTURE_CATALOG_SCHEMA_VERSION = 1
TEXTURE_FORMAT = "nitro_pltt16_4bpp"
TEXTURE_WIDTH = 32
TEXTURE_HEIGHT = 32
MAX_SOURCE_BYTES = 131_072
MAX_COLORS = 16
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SAFE_ENTRY = re.compile(r"^[A-Za-z0-9_]{1,15}$")
SUPPORTED_ROM_SHA256 = "65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105"
STAGE4D_AREA_TEXTURE_ARCHIVE = "a/0/4/4"
STAGE4D_AREA_TEXTURE_ARCHIVE_SHA256 = "6385837c11139c543884434a54768e7279b485214b7ca309cf8a670d8f98d647"
STAGE4D_TEMPLATE_MEMBER = 2
STAGE4D_TEMPLATE_MEMBER_SHA256 = "bfecfce0640b92a69c32fe4339cafc5a77a088a668a66f67b12e6be8cf727de1"


class TextureError(ValueError):
    """A PNG, texture declaration, or bounded TEX0 target is unsupported."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


@dataclass(frozen=True)
class NitroTextureEntry:
    index: int
    name: str
    image_offset: int
    params: int
    format: int
    width: int
    height: int
    byte_length: int


@dataclass(frozen=True)
class NitroPaletteEntry:
    index: int
    name: str
    data_offset: int
    byte_capacity: int
    flag: int


@dataclass(frozen=True)
class TEX0Layout:
    file_size: int
    tex0_offset: int
    texture_data_offset: int
    texture_data_size: int
    palette_data_offset: int
    palette_data_size: int
    textures: tuple[NitroTextureEntry, ...]
    palettes: tuple[NitroPaletteEntry, ...]


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise TextureError("malformed_texture_container", "u16 read leaves the BTX0 container")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise TextureError("malformed_texture_container", "u32 read leaves the BTX0 container")
    return struct.unpack_from("<I", data, offset)[0]


def _name(data: bytes, offset: int) -> str:
    if offset < 0 or offset + 16 > len(data):
        raise TextureError("malformed_texture_dictionary", "dictionary name leaves the BTX0 container")
    raw = data[offset:offset + 16].split(b"\0", 1)[0]
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise TextureError("malformed_texture_dictionary", "dictionary name is not ASCII") from error


def _texture_byte_length(texture_format: int, width: int, height: int) -> int:
    # Stage 4C accepts only GX_TEXFMT_PLTT16 (format field 3): four bits/texel.
    if texture_format != 3:
        raise TextureError(
            "unsupported_texture_format", f"target texture format {texture_format} is not PLTT16",
        )
    return width * height // 2


def parse_btx0(data: bytes) -> TEX0Layout:
    """Parse the exact NNS resource dictionaries needed for in-place payload replacement."""
    if len(data) < 0x50 or data[:4] != b"BTX0":
        raise TextureError("malformed_texture_container", "texture container must begin with BTX0")
    if _u32(data, 8) != len(data) or _u16(data, 0x0C) != 0x10 or _u16(data, 0x0E) != 1:
        raise TextureError("malformed_texture_container", "BTX0 header size/section metadata is inconsistent")
    tex0 = _u32(data, 0x10)
    if tex0 + 0x3C > len(data) or data[tex0:tex0 + 4] != b"TEX0":
        raise TextureError("malformed_texture_container", "BTX0 does not contain the expected TEX0 section")
    if tex0 + _u32(data, tex0 + 4) != len(data):
        raise TextureError("malformed_texture_container", "TEX0 section length is inconsistent")

    texture_info = tex0 + _u16(data, tex0 + 0x0E)
    texture_data = tex0 + _u32(data, tex0 + 0x14)
    palette_info = tex0 + _u32(data, tex0 + 0x34)
    palette_data = tex0 + _u32(data, tex0 + 0x38)
    texture_size = _u16(data, tex0 + 0x0C) * 8
    palette_size = (_u32(data, tex0 + 0x30) & 0x7FFFFFFF) * 8
    if not (tex0 <= texture_info < palette_info <= texture_data <= palette_data <= len(data)):
        raise TextureError("malformed_texture_container", "TEX0 offsets are not monotonic")
    if texture_data + texture_size > len(data) or palette_data + palette_size > len(data):
        raise TextureError("malformed_texture_container", "TEX0 payload sizes exceed the container")

    texture_count = data[texture_info + 1]
    texture_properties = texture_info + 4 + _u16(data, texture_info + 6)
    texture_names = texture_properties + texture_count * 8
    if texture_properties < texture_info or texture_names + texture_count * 16 > palette_info:
        raise TextureError("malformed_texture_dictionary", "texture dictionary tables exceed their section")
    textures: list[NitroTextureEntry] = []
    for index in range(texture_count):
        record = texture_properties + index * 8
        image_units, params = struct.unpack_from("<HH", data, record)
        width = 8 << ((params >> 4) & 7)
        height = 8 << ((params >> 7) & 7)
        texture_format = (params >> 10) & 7
        byte_length = _texture_byte_length(texture_format, width, height) if texture_format == 3 else 0
        image_offset = texture_data + image_units * 8
        if (image_offset - texture_data) % 8 or image_offset < texture_data or image_offset + byte_length > texture_data + texture_size:
            raise TextureError("invalid_texture_offset", f"texture index {index} leaves the aligned texture payload")
        textures.append(NitroTextureEntry(
            index=index,
            name=_name(data, texture_names + index * 16),
            image_offset=image_offset,
            params=params,
            format=texture_format,
            width=width,
            height=height,
            byte_length=byte_length,
        ))

    palette_count = data[palette_info + 1]
    palette_properties = palette_info + 0x0C
    palette_names = palette_properties + 4 + palette_count * 8
    palette_offsets = palette_names - palette_count * 4
    if palette_offsets < palette_info or palette_names + palette_count * 16 > texture_data:
        raise TextureError("malformed_texture_dictionary", "palette dictionary tables exceed their section")
    raw_palettes: list[tuple[int, str, int, int]] = []
    for index in range(palette_count):
        offset_units = _u16(data, palette_offsets + index * 4)
        flag = _u16(data, palette_offsets + index * 4 + 2)
        raw_palettes.append((index, _name(data, palette_names + index * 16), offset_units * 8, flag))
    distinct_offsets = sorted({offset for _index, _entry_name, offset, _flag in raw_palettes} | {palette_size})
    palettes = []
    for index, entry_name, offset, flag in raw_palettes:
        if offset >= palette_size:
            raise TextureError("malformed_texture_dictionary", f"palette {entry_name!r} starts outside palette data")
        next_offset = next(candidate for candidate in distinct_offsets if candidate > offset)
        if offset % 8 or next_offset > palette_size:
            raise TextureError("invalid_palette_offset", f"palette {entry_name!r} leaves the aligned palette payload")
        palettes.append(NitroPaletteEntry(
            index=index,
            name=entry_name,
            data_offset=palette_data + offset,
            byte_capacity=next_offset - offset,
            flag=flag,
        ))

    if len({entry.name for entry in textures}) != len(textures) or len({entry.name for entry in palettes}) != len(palettes):
        raise TextureError("malformed_texture_dictionary", "texture/palette dictionary names must be unique")
    return TEX0Layout(
        file_size=len(data), tex0_offset=tex0,
        texture_data_offset=texture_data, texture_data_size=texture_size,
        palette_data_offset=palette_data, palette_data_size=palette_size,
        textures=tuple(textures), palettes=tuple(palettes),
    )


def validate_texture_spec(spec: object, root: Path) -> dict[str, Any]:
    common = {
        "schema_version", "id", "source", "source_format", "format", "dimensions",
        "alpha_policy", "quantization",
    }
    if not isinstance(spec, dict) or spec.get("schema_version") not in {
        TEXTURE_SCHEMA_VERSION, PROJECT_TEXTURE_SCHEMA_VERSION,
    }:
        raise TextureError("invalid_texture_spec", "texture declaration has unsupported or missing fields")
    expected = common | ({"container"} if spec["schema_version"] == TEXTURE_SCHEMA_VERSION else set())
    if set(spec) != expected:
        raise TextureError("invalid_texture_spec", "texture declaration has unsupported or missing fields")
    if not isinstance(spec.get("id"), str) or not SAFE_ID.fullmatch(spec["id"]):
        raise TextureError("invalid_texture_id", "texture id must be stable lower snake_case")
    source_value = spec.get("source")
    if not isinstance(source_value, str) or not source_value:
        raise TextureError("invalid_texture_source", "texture source must be a repository-relative PNG path")
    source_relative = Path(source_value)
    if source_relative.is_absolute() or ".." in source_relative.parts:
        raise TextureError("unsafe_texture_path", "texture source path escapes the repository")
    source = (root / source_relative).resolve()
    try:
        source.relative_to((root / "assets/textures").resolve())
    except ValueError as error:
        raise TextureError("unsafe_texture_path", "texture source must remain under assets/textures") from error
    if source.suffix.lower() != ".png" or spec.get("source_format") != "png":
        raise TextureError("unsupported_image_extension", "Stage 4C supports PNG source only")
    if not source.is_file():
        raise TextureError("missing_png", f"texture PNG does not exist: {source_value}")
    if spec.get("format") != TEXTURE_FORMAT:
        raise TextureError("unsupported_texture_format", f"Stage 4C supports only {TEXTURE_FORMAT}")
    if spec.get("dimensions") != [TEXTURE_WIDTH, TEXTURE_HEIGHT]:
        raise TextureError("unsupported_texture_dimensions", "Stage 4C texture declaration must be 32x32")
    if spec.get("alpha_policy") != "opaque":
        raise TextureError("invalid_transparency", "Stage 4C supports fully opaque PNGs only")
    if spec.get("quantization") != "exact_bgr555_palette_16":
        raise TextureError("unsupported_quantization", "Stage 4C uses exact deterministic BGR555 palette mapping")
    if spec["schema_version"] == PROJECT_TEXTURE_SCHEMA_VERSION:
        return json.loads(json.dumps(spec, sort_keys=True))
    container = spec.get("container")
    container_fields = {
        "archive", "archive_sha256", "member", "member_sha256", "texture_entry", "palette_entry",
    }
    if not isinstance(container, dict) or set(container) != container_fields:
        raise TextureError("invalid_texture_container", "texture target container declaration is incomplete")
    if container["archive"] != "a/0/4/4" or container["member"] != 2:
        raise TextureError("unsupported_texture_slot", "Stage 4C is bounded to area texture archive member 2")
    for field in ("archive_sha256", "member_sha256"):
        if not isinstance(container[field], str) or not re.fullmatch(r"[0-9a-f]{64}", container[field]):
            raise TextureError("invalid_texture_container", f"container {field} must be a SHA-256")
    for field in ("texture_entry", "palette_entry"):
        if not isinstance(container[field], str) or not SAFE_ENTRY.fullmatch(container[field]):
            raise TextureError("invalid_texture_entry", f"container {field} is not a bounded Nitro name")
    if container["texture_entry"] != "road01_r" or container["palette_entry"] != "road01_r":
        raise TextureError("unsupported_texture_slot", "Stage 4C is bounded to the dedicated road01_r payload pair")
    return json.loads(json.dumps(spec, sort_keys=True))


def rgb888_to_bgr555(red: int, green: int, blue: int) -> int:
    """Encode an opaque RGB888 color as little-endian Nitro/GX RGB5 bits."""
    for channel in (red, green, blue):
        if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255:
            raise TextureError("invalid_color", "RGB channels must be bytes")
    return (red >> 3) | ((green >> 3) << 5) | ((blue >> 3) << 10)


def compile_png(spec: dict[str, Any], root: Path) -> dict[str, Any]:
    spec = validate_texture_spec(spec, root)
    source = (root / spec["source"]).resolve()
    source_bytes = source.read_bytes()
    if len(source_bytes) > MAX_SOURCE_BYTES:
        raise TextureError("image_too_large", "PNG exceeds the Stage 4C source byte budget")
    try:
        with Image.open(source) as opened:
            opened.verify()
        with Image.open(source) as opened:
            mode = opened.mode
            dimensions = opened.size
            if mode not in ("RGB", "RGBA"):
                raise TextureError("unsupported_color_mode", f"PNG mode {mode!r} is unsupported")
            if dimensions != (TEXTURE_WIDTH, TEXTURE_HEIGHT):
                raise TextureError(
                    "dimension_mismatch", f"PNG dimensions {dimensions} do not match the 32x32 target slot",
                )
            rgba = opened.convert("RGBA")
            pixels = list(rgba.get_flattened_data())
    except TextureError:
        raise
    except (OSError, SyntaxError, UnidentifiedImageError) as error:
        raise TextureError("invalid_png", f"cannot decode PNG: {error}") from error
    if any(alpha != 255 for _red, _green, _blue, alpha in pixels):
        raise TextureError("invalid_transparency", "Stage 4C proof texture must be fully opaque")

    encoded_pixels = [rgb888_to_bgr555(red, green, blue) for red, green, blue, _alpha in pixels]
    palette_values = sorted(set(encoded_pixels))
    if len(palette_values) > MAX_COLORS:
        raise TextureError(
            "palette_overflow", f"PNG has {len(palette_values)} distinct BGR555 colors; Stage 4C permits 16",
            color_count=len(palette_values), maximum=MAX_COLORS,
        )
    palette_index = {color: index for index, color in enumerate(palette_values)}
    indices = [palette_index[color] for color in encoded_pixels]
    texels = bytes(indices[index] | (indices[index + 1] << 4) for index in range(0, len(indices), 2))
    palette = b"".join(struct.pack("<H", color) for color in palette_values)
    palette += bytes(MAX_COLORS * 2 - len(palette))
    ir = {
        "schema_version": 1,
        "texture_id": spec["id"],
        "width": TEXTURE_WIDTH,
        "height": TEXTURE_HEIGHT,
        "source_mode": mode,
        "alpha_policy": "opaque",
        "format": TEXTURE_FORMAT,
        "bits_per_pixel": 4,
        "texel_order": "row_major_left_pixel_low_nibble",
        "palette_encoding": "little_endian_bgr555_bit15_clear",
        "palette_values": palette_values,
        "texel_indices": indices,
    }
    semantic_ir = (json.dumps(ir, sort_keys=True, separators=(",", ":")) + "\n").encode()
    report = {
        "schema_version": 1,
        "success": True,
        "texture_id": spec["id"],
        "source": spec["source"],
        "source_sha256": _hash(source_bytes),
        "dimensions": [TEXTURE_WIDTH, TEXTURE_HEIGHT],
        "source_mode": mode,
        "source_color_count": len(set(pixels)),
        "encoded_color_count": len(palette_values),
        "transparency_used": False,
        "format": TEXTURE_FORMAT,
        "bits_per_pixel": 4,
        "texture_bytes": len(texels),
        "palette_entries": MAX_COLORS,
        "palette_bytes": len(palette),
        "quantization": "exact RGB888-to-BGR555 truncation; stable ascending encoded palette; no reduction",
        "container": spec.get("container"),
        "hashes": {
            "image_ir_sha256": _hash(semantic_ir),
            "texture_sha256": _hash(texels),
            "palette_sha256": _hash(palette),
        },
    }
    return {"spec": spec, "ir": ir, "texture": texels, "palette": palette, "report": report}


def load_texture_catalog(path: Path, root: Path) -> dict[str, Any]:
    """Load the persistent Stage 4D texture allocation catalog."""
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TextureError("texture_catalog_unreadable", f"cannot read texture catalog {path}: {error}") from error
    expected = {"schema_version", "target", "template", "textures"}
    if not isinstance(data, dict) or set(data) != expected or data.get("schema_version") != TEXTURE_CATALOG_SCHEMA_VERSION:
        raise TextureError("invalid_texture_catalog", "texture catalog must use Stage 4D schema 1")
    target = data.get("target")
    if target != {
        "game_code": "IPKE", "region": "US", "rom_sha256": SUPPORTED_ROM_SHA256,
        "area_texture_archive": STAGE4D_AREA_TEXTURE_ARCHIVE,
        "area_texture_archive_sha256": STAGE4D_AREA_TEXTURE_ARCHIVE_SHA256,
        "pristine_member_count": 106, "project_member": 106,
    }:
        raise TextureError("unsupported_container_revision", "texture catalog target is not the supported US HG append boundary")
    template = data.get("template")
    if template != {
        "member": STAGE4D_TEMPLATE_MEMBER,
        "member_sha256": STAGE4D_TEMPLATE_MEMBER_SHA256,
        "policy": "metadata_only_zero_payload_project_member",
    }:
        raise TextureError("unsupported_container_revision", "texture catalog template metadata is not hash locked")
    textures = data.get("textures")
    if not isinstance(textures, list) or len(textures) < 2:
        raise TextureError("invalid_texture_catalog", "Stage 4D catalog requires at least two project textures")
    seen_symbols: set[str] = set()
    seen_names: set[str] = set()
    seen_slots: set[tuple[int, int]] = set()
    allocations: list[int] = []
    validated: list[dict[str, Any]] = []
    for entry in textures:
        required = {"allocation", "nitro_texture", "nitro_palette", "texture_slot", "palette_slot", "texture"}
        if not isinstance(entry, dict) or set(entry) != required:
            raise TextureError("malformed_texture_allocation", "texture allocation entry has unsupported fields")
        allocation = entry["allocation"]
        if isinstance(allocation, bool) or not isinstance(allocation, int) or allocation < 0:
            raise TextureError("invalid_texture_allocation", "texture allocation must be a non-negative persistent integer")
        spec = validate_texture_spec(entry["texture"], root)
        if spec["schema_version"] != PROJECT_TEXTURE_SCHEMA_VERSION:
            raise TextureError("invalid_texture_catalog", "catalog textures must use project texture schema 2")
        names = (entry["nitro_texture"], entry["nitro_palette"])
        if any(not isinstance(name, str) or not SAFE_ENTRY.fullmatch(name) for name in names):
            raise TextureError("texture_name_overflow", "physical Nitro names must be 1-15 ASCII identifier bytes")
        slots = (entry["texture_slot"], entry["palette_slot"])
        if any(isinstance(slot, bool) or not isinstance(slot, int) or slot < 0 for slot in slots):
            raise TextureError("invalid_texture_allocation", "physical dictionary slots must be non-negative integers")
        if spec["id"] in seen_symbols:
            raise TextureError("duplicate_texture_symbol", f"duplicate project texture symbol {spec['id']!r}")
        if names[0] in seen_names or names[1] in seen_names:
            raise TextureError("duplicate_physical_name", "a physical Nitro texture/palette name is allocated twice")
        if slots in seen_slots:
            raise TextureError("duplicate_texture_payload", "two project textures share one writable slot pair")
        seen_symbols.add(spec["id"])
        seen_names.update(names)
        seen_slots.add(slots)
        allocations.append(allocation)
        validated.append({**entry, "texture": spec})
    if len(set(allocations)) != len(allocations):
        raise TextureError("duplicate_texture_allocation", "persistent texture allocation numbers must be unique")
    if sorted(allocations) != list(range(len(allocations))):
        raise TextureError("unstable_texture_allocation", "persistent texture allocations must be contiguous from zero")
    normalized = {**data, "textures": sorted(validated, key=lambda entry: entry["allocation"])}
    normalized["catalog_sha256"] = _hash(raw)
    return normalized


def compile_texture_catalog(path: Path, root: Path) -> dict[str, Any]:
    catalog = load_texture_catalog(path, root)
    bindings: dict[str, list[dict[str, str]]] = {
        entry["texture"]["id"]: [] for entry in catalog["textures"]
    }
    asset_catalog_path = root / "assets/catalog.json"
    if asset_catalog_path.is_file():
        try:
            asset_catalog = json.loads(asset_catalog_path.read_text(encoding="utf-8"))
            for asset_entry in asset_catalog.get("assets", []):
                manifest_path = (root / asset_entry["manifest"]).resolve()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("schema_version") not in (3, 4, 5):
                    continue
                declared_catalog = (root / manifest.get("texture_catalog", "")).resolve()
                if declared_catalog != path.resolve():
                    continue
                for source_material, mapping in sorted(manifest["material_policy"]["mappings"].items()):
                    symbol = mapping["texture"]
                    if symbol in bindings:
                        bindings[symbol].append({
                            "asset": manifest["id"], "source_material": source_material,
                            "material_alias": mapping["alias"],
                        })
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise TextureError("invalid_asset_texture_binding", f"cannot inspect asset texture bindings: {error}") from error
    compiled: dict[str, dict[str, Any]] = {}
    allocation_report = []
    for entry in catalog["textures"]:
        texture = compile_png(entry["texture"], root)
        symbol = texture["spec"]["id"]
        compiled[symbol] = texture
        allocation_report.append({
            "symbol": symbol, "allocation": entry["allocation"],
            "nitro_texture": entry["nitro_texture"], "nitro_palette": entry["nitro_palette"],
            "texture_slot": entry["texture_slot"], "palette_slot": entry["palette_slot"],
            "source": texture["spec"]["source"], "source_sha256": texture["report"]["source_sha256"],
            "texture_sha256": texture["report"]["hashes"]["texture_sha256"],
            "palette_sha256": texture["report"]["hashes"]["palette_sha256"],
            "bindings": bindings[symbol],
        })
    semantic = {"schema_version": 1, "allocations": allocation_report}
    return {
        "catalog": catalog, "textures": compiled,
        "report": {
            "schema_version": 1, "success": True, "catalog": str(path),
            "catalog_sha256": catalog["catalog_sha256"], "texture_count": len(compiled),
            "physical_container": {
                "archive": catalog["target"]["area_texture_archive"],
                "member": catalog["target"]["project_member"],
                "provenance": "PROJECT_APPENDED",
            },
            "allocations": allocation_report,
            "allocation_sha256": _hash((json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n").encode()),
        },
    }


def build_project_btx0(template_data: bytes, compiled_catalog: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Build one project-owned member while preserving only verified TEX0 layout metadata."""
    catalog = compiled_catalog["catalog"]
    if _hash(template_data) != catalog["template"]["member_sha256"]:
        raise TextureError("texture_container_hash_mismatch", "project BTX0 template hash is unsupported")
    layout = parse_btx0(template_data)
    output = bytearray(template_data)
    texture_region = range(layout.texture_data_offset, layout.texture_data_offset + layout.texture_data_size)
    palette_region = range(layout.palette_data_offset, layout.palette_data_offset + layout.palette_data_size)
    output[texture_region.start:texture_region.stop] = bytes(layout.texture_data_size)
    output[palette_region.start:palette_region.stop] = bytes(layout.palette_data_size)
    used_ranges: list[tuple[int, int, str]] = []
    entries_report = []
    for entry in catalog["textures"]:
        symbol = entry["texture"]["id"]
        compiled = compiled_catalog["textures"][symbol]
        if entry["texture_slot"] >= len(layout.textures) or entry["palette_slot"] >= len(layout.palettes):
            raise TextureError("container_overflow", f"allocation {symbol!r} leaves the verified dictionary")
        texture = layout.textures[entry["texture_slot"]]
        palette = layout.palettes[entry["palette_slot"]]
        if texture.name != entry["nitro_texture"] or palette.name != entry["nitro_palette"]:
            raise TextureError("malformed_dictionary_entry", f"allocation {symbol!r} disagrees with template dictionary names")
        if (texture.format, texture.width, texture.height, texture.byte_length) != (3, 32, 32, 512):
            raise TextureError("unsupported_texture_slot", f"allocation {symbol!r} does not target a 32x32 PLTT16 entry")
        if palette.byte_capacity != 32:
            raise TextureError("unsupported_palette_slot", f"allocation {symbol!r} does not target a 16-color palette entry")
        ranges = (
            (texture.image_offset, texture.image_offset + texture.byte_length, f"{symbol}:texture"),
            (palette.data_offset, palette.data_offset + palette.byte_capacity, f"{symbol}:palette"),
        )
        for start, end, label in ranges:
            if any(start < other_end and other_start < end for other_start, other_end, _ in used_ranges):
                raise TextureError("overlapping_payloads", f"project payload {label} overlaps another allocation")
            used_ranges.append((start, end, label))
        output[texture.image_offset:texture.image_offset + texture.byte_length] = compiled["texture"]
        output[palette.data_offset:palette.data_offset + palette.byte_capacity] = compiled["palette"]
        entries_report.append({
            "symbol": symbol, "allocation": entry["allocation"],
            "texture": {"index": texture.index, "name": texture.name, "offset": texture.image_offset,
                        "bytes": texture.byte_length, "sha256": _hash(compiled["texture"])},
            "palette": {"index": palette.index, "name": palette.name, "offset": palette.data_offset,
                        "bytes": palette.byte_capacity, "sha256": _hash(compiled["palette"])},
        })
    project = bytes(output)
    reparsed = parse_btx0(project)
    if reparsed != layout:
        raise TextureError("texture_dictionary_changed", "project rebuild changed verified dictionary/layout metadata")
    metadata_indices = set(range(len(template_data))) - set(texture_region) - set(palette_region)
    if any(template_data[index] != project[index] for index in metadata_indices):
        raise TextureError("unrelated_container_change", "project rebuild changed bytes outside payload regions")
    return project, {
        "schema_version": 1, "success": True,
        "architecture": "appended_project_member_hash_locked_metadata_zeroed_payloads",
        "template_member_sha256": _hash(template_data), "project_member_sha256": _hash(project),
        "container_bytes": len(project),
        "dictionary_counts": {"textures": len(layout.textures), "palettes": len(layout.palettes)},
        "project_entry_count": len(entries_report), "project_entries": entries_report,
        "texture_payload_bytes": layout.texture_data_size, "palette_payload_bytes": layout.palette_data_size,
        "inherited_payload_bytes_copied": 0, "dictionary_layout_unchanged": True,
        "parser_reopen_succeeded": True,
    }


def compile_texture_catalog_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    compiled = compile_texture_catalog(path, root)
    output.mkdir(parents=True, exist_ok=True)
    for symbol, texture in sorted(compiled["textures"].items()):
        child = output / symbol
        child.mkdir(parents=True, exist_ok=True)
        (child / "texture-ir.json").write_text(json.dumps(texture["ir"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (child / "texture.bin").write_bytes(texture["texture"])
        (child / "palette.bin").write_bytes(texture["palette"])
    report = dict(compiled["report"])
    report["outputs"] = {"textures": "./", "report": "texture-catalog-report.json"}
    (output / "texture-catalog-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def patch_btx0(data: bytes, compiled: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    spec = compiled["spec"]
    container = spec["container"]
    if _hash(data) != container["member_sha256"]:
        raise TextureError(
            "texture_container_hash_mismatch", "area texture member does not match the supported US HG template",
            expected=container["member_sha256"], actual=_hash(data),
        )
    layout = parse_btx0(data)
    texture_by_name = {entry.name: entry for entry in layout.textures}
    palette_by_name = {entry.name: entry for entry in layout.palettes}
    texture = texture_by_name.get(container["texture_entry"])
    palette = palette_by_name.get(container["palette_entry"])
    if texture is None or palette is None:
        raise TextureError("missing_texture_entry", "target texture/palette dictionary entry does not exist")
    if (texture.format, texture.width, texture.height, texture.byte_length) != (3, 32, 32, 512):
        raise TextureError("texture_slot_mismatch", "road01_r texture metadata is not the verified PLTT16 32x32 slot")
    if palette.byte_capacity != 32:
        raise TextureError(
            "palette_slot_mismatch", f"road01_r palette capacity is {palette.byte_capacity}, expected 32",
        )
    if len(compiled["texture"]) != texture.byte_length or len(compiled["palette"]) != palette.byte_capacity:
        raise TextureError("encoded_byte_length_mismatch", "compiled payload does not exactly fill its verified slots")

    texture_range = range(texture.image_offset, texture.image_offset + texture.byte_length)
    palette_range = range(palette.data_offset, palette.data_offset + palette.byte_capacity)
    output = bytearray(data)
    output[texture_range.start:texture_range.stop] = compiled["texture"]
    output[palette_range.start:palette_range.stop] = compiled["palette"]
    patched = bytes(output)
    parsed = parse_btx0(patched)
    if parsed != layout:
        raise TextureError(
            "texture_dictionary_changed",
            "in-place payload replacement changed TEX0 dictionaries, offsets, or capacities",
        )
    changed = [index for index, (before, after) in enumerate(zip(data, patched, strict=True)) if before != after]
    allowed = set(texture_range) | set(palette_range)
    if any(index not in allowed for index in changed):
        raise TextureError("unrelated_container_change", "texture patch modified bytes outside its payload slots")
    if patched[texture_range.start:texture_range.stop] != compiled["texture"]:
        raise TextureError("texture_patch_mismatch", "patched texture bytes do not match compiler output")
    if patched[palette_range.start:palette_range.stop] != compiled["palette"]:
        raise TextureError("palette_patch_mismatch", "patched palette bytes do not match compiler output")
    report = {
        "schema_version": 1,
        "success": True,
        "source_member_sha256": _hash(data),
        "patched_member_sha256": _hash(patched),
        "container_bytes": len(patched),
        "texture_entry": {
            "index": texture.index, "name": texture.name, "format": texture.format,
            "width": texture.width, "height": texture.height,
            "offset": texture.image_offset, "bytes": texture.byte_length,
        },
        "palette_entry": {
            "index": palette.index, "name": palette.name, "offset": palette.data_offset,
            "bytes": palette.byte_capacity, "flag": palette.flag,
        },
        "dictionary_counts": {"textures": len(parsed.textures), "palettes": len(parsed.palettes)},
        "dictionary_layout_unchanged": True,
        "changed_byte_count": len(changed),
        "unrelated_bytes_unchanged": True,
        "hashes": {
            "texture_sha256": _hash(compiled["texture"]),
            "palette_sha256": _hash(compiled["palette"]),
            "patched_member_sha256": _hash(patched),
        },
    }
    return patched, report


def compile_texture_outputs(spec: dict[str, Any], output: Path, root: Path) -> dict[str, Any]:
    compiled = compile_png(spec, root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "texture-ir.json").write_text(json.dumps(compiled["ir"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "texture.bin").write_bytes(compiled["texture"])
    (output / "palette.bin").write_bytes(compiled["palette"])
    report = dict(compiled["report"])
    report["outputs"] = {
        "texture_ir": "texture-ir.json", "texture": "texture.bin",
        "palette": "palette.bin", "report": "texture-report.json",
    }
    (output / "texture-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
