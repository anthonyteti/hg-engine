"""Stable symbolic resource registry for the deterministic world compiler.

The registry intentionally separates numeric slot provenance from binary
serialization. Existing allocations are persistent records; new allocations
may consume explicitly classified KNOWN_FREE slots or revision-locked,
contiguous APPEND_PROVEN NARC windows.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = PROJECT_ROOT / "world" / "registry.json"
DEFAULT_INVENTORY = PROJECT_ROOT / "build" / "registry" / "slot-inventory.json"
CLASSIFICATIONS = {
    "APPEND_PROVEN",
    "HEADER_EXPANSION_PROVEN",
    "KNOWN_FREE",
    "CONTROLLED_REPLACEMENT",
    "ENGINE_OWNED",
    "PROJECT_APPENDED",
    "PROJECT_HEADER",
    "PROJECT_ALLOCATED",
    "VANILLA_OWNED",
    "RESERVED",
    "UNKNOWN",
}
WRITABLE_CLASSIFICATIONS = {
    "KNOWN_FREE", "CONTROLLED_REPLACEMENT", "PROJECT_ALLOCATED", "PROJECT_APPENDED", "PROJECT_HEADER",
}
SYMBOL_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class RegistryError(ValueError):
    """A registry or symbolic world reference violates the allocation contract."""

    def __init__(self, code: str, message: str, **details: object):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), **self.details}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistryError("registry_unreadable", f"cannot load registry {path}: {error}") from error
    if not isinstance(value, dict):
        raise RegistryError("invalid_registry", "registry root must be an object")
    return value


def _slot_classification(namespace: dict[str, Any], numeric_id: int) -> tuple[str, dict[str, Any]]:
    override = namespace.get("slot_overrides", {}).get(str(numeric_id))
    if override is not None:
        return override["classification"], override
    for range_spec in namespace.get("ranges", []):
        if range_spec["start"] <= numeric_id <= range_spec["end"]:
            return range_spec["classification"], range_spec
    return "UNKNOWN", {"classification": "UNKNOWN", "evidence": "no classified range"}


def _range_classification(namespace: dict[str, Any], numeric_id: int) -> tuple[str, dict[str, Any]]:
    """Return range provenance without allowing a persistent override to hide it."""
    for range_spec in namespace.get("ranges", []):
        if range_spec["start"] <= numeric_id <= range_spec["end"]:
            return range_spec["classification"], range_spec
    return "UNKNOWN", {"classification": "UNKNOWN", "evidence": "no classified range"}


def validate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema_version") != 1:
        raise RegistryError("unsupported_schema", "registry schema_version must be 1")
    target = registry.get("target")
    if not isinstance(target, dict) or target.get("game_code") != "IPKE":
        raise RegistryError("invalid_target", "registry target must identify US HeartGold game code IPKE")
    for key in ("rom_sha256", "arm9_sha256"):
        value = target.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RegistryError("invalid_target", f"registry target {key} must be a lowercase SHA-256")

    namespaces = registry.get("namespaces")
    if not isinstance(namespaces, dict) or not namespaces:
        raise RegistryError("invalid_namespaces", "registry namespaces must be a non-empty object")

    symbols: dict[str, tuple[str, dict[str, Any]]] = {}
    numeric_owners: dict[tuple[str, int], tuple[str, str]] = {}
    append_domains: dict[str, dict[str, Any]] = {}
    for namespace_name in sorted(namespaces):
        namespace = namespaces[namespace_name]
        if not SYMBOL_PATTERN.fullmatch(namespace_name):
            raise RegistryError("invalid_namespace", f"invalid namespace name {namespace_name!r}")
        if not isinstance(namespace, dict):
            raise RegistryError("invalid_namespace", f"namespace {namespace_name} must be an object")
        numeric_min = namespace.get("numeric_min")
        numeric_max = namespace.get("numeric_max")
        if not isinstance(numeric_min, int) or not isinstance(numeric_max, int) or numeric_min < 0 or numeric_min > numeric_max:
            raise RegistryError("invalid_range", f"namespace {namespace_name} has invalid numeric bounds")
        collision_domain = namespace.get("collision_domain")
        if not isinstance(collision_domain, str) or not collision_domain:
            raise RegistryError("invalid_namespace", f"namespace {namespace_name} needs a collision_domain")

        append = namespace.get("append")
        if append is not None:
            if not isinstance(append, dict) or set(append) != {
                "archive", "pristine_count", "allocation_start", "proven_max_id", "policy",
            }:
                raise RegistryError("invalid_append_policy", f"namespace {namespace_name} has malformed append metadata")
            archive_name = append.get("archive")
            pristine_count = append.get("pristine_count")
            allocation_start = append.get("allocation_start")
            proven_max_id = append.get("proven_max_id")
            archive = target.get("archives", {}).get(archive_name)
            if (
                archive is None or not isinstance(pristine_count, int) or not isinstance(allocation_start, int)
                or not isinstance(proven_max_id, int) or pristine_count != archive.get("members")
                or allocation_start < pristine_count or proven_max_id < allocation_start
                or append.get("policy") != "contiguous_from_pristine_count"
            ):
                raise RegistryError(
                    "append_evidence_mismatch",
                    f"namespace {namespace_name} append policy disagrees with pristine archive evidence",
                )
            domain_evidence = {
                "archive": archive_name,
                "pristine_count": pristine_count,
                "allocation_start": allocation_start,
                "proven_max_id": proven_max_id,
            }
            previous = append_domains.setdefault(collision_domain, domain_evidence)
            if previous != domain_evidence:
                raise RegistryError(
                    "append_evidence_mismatch",
                    f"collision domain {collision_domain} has inconsistent append evidence",
                )

        header_expansion = namespace.get("header_expansion")
        if header_expansion is not None:
            expected_keys = {"retail_count", "entry_size", "allocation_start", "proven_max_id", "policy"}
            if not isinstance(header_expansion, dict) or set(header_expansion) != expected_keys:
                raise RegistryError("invalid_header_expansion", f"namespace {namespace_name} has malformed expansion metadata")
            if (
                namespace_name != "map_headers"
                or header_expansion["retail_count"] != 540
                or header_expansion["entry_size"] != 24
                or header_expansion["allocation_start"] != 540
                or not isinstance(header_expansion["proven_max_id"], int)
                or header_expansion["proven_max_id"] < 540
                or header_expansion["policy"] != "contiguous_from_retail_boundary"
            ):
                raise RegistryError("header_expansion_evidence_mismatch", "map-header expansion policy disagrees with verified retail layout")
        previous_end = numeric_min - 1
        for range_spec in namespace.get("ranges", []):
            if not isinstance(range_spec, dict):
                raise RegistryError("invalid_range", f"namespace {namespace_name} contains a malformed range")
            start, end = range_spec.get("start"), range_spec.get("end")
            classification = range_spec.get("classification")
            if (
                not isinstance(start, int) or not isinstance(end, int)
                or start < numeric_min or end > numeric_max or start > end or start <= previous_end
                or classification not in CLASSIFICATIONS
            ):
                raise RegistryError("invalid_range", f"namespace {namespace_name} contains overlapping or invalid ranges")
            previous_end = end

        overrides = namespace.get("slot_overrides", {})
        if not isinstance(overrides, dict):
            raise RegistryError("invalid_override", f"namespace {namespace_name} slot_overrides must be an object")
        for raw_id, override in overrides.items():
            try:
                numeric_id = int(raw_id)
            except ValueError as error:
                raise RegistryError("invalid_override", f"namespace {namespace_name} override {raw_id!r} is not numeric") from error
            if str(numeric_id) != raw_id or not numeric_min <= numeric_id <= numeric_max:
                raise RegistryError("invalid_override", f"namespace {namespace_name} override {raw_id!r} is out of bounds")
            if not isinstance(override, dict) or override.get("classification") not in CLASSIFICATIONS:
                raise RegistryError("invalid_override", f"namespace {namespace_name} override {raw_id} has invalid classification")
            if not isinstance(override.get("evidence"), str) or not override["evidence"]:
                raise RegistryError("missing_evidence", f"namespace {namespace_name} override {raw_id} needs evidence")
            if override["classification"] == "PROJECT_APPENDED":
                if append is None:
                    raise RegistryError("unproven_append", f"namespace {namespace_name} cannot own appended members")
                underlying, _ = _range_classification(namespace, numeric_id)
                if (
                    underlying != "APPEND_PROVEN"
                    or numeric_id < append["allocation_start"]
                    or numeric_id > append["proven_max_id"]
                ):
                    raise RegistryError(
                        "invalid_appended_id",
                        f"namespace {namespace_name} appended ID {numeric_id} is outside its proven window",
                    )
            if override["classification"] == "PROJECT_HEADER":
                if header_expansion is None:
                    raise RegistryError("unproven_header_expansion", f"namespace {namespace_name} cannot own project headers")
                underlying, _ = _range_classification(namespace, numeric_id)
                if (
                    underlying != "HEADER_EXPANSION_PROVEN"
                    or numeric_id < header_expansion["allocation_start"]
                    or numeric_id > header_expansion["proven_max_id"]
                ):
                    raise RegistryError("invalid_project_header", f"project header {numeric_id} is outside its proven window")

        resources = namespace.get("resources", [])
        if not isinstance(resources, list):
            raise RegistryError("invalid_resources", f"namespace {namespace_name} resources must be a list")
        for resource in resources:
            if not isinstance(resource, dict) or set(resource) - {"symbol", "id", "access", "note"}:
                raise RegistryError("invalid_resource", f"namespace {namespace_name} contains a malformed resource")
            symbol, numeric_id = resource.get("symbol"), resource.get("id")
            access = resource.get("access", "write")
            if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
                raise RegistryError("invalid_symbol", f"namespace {namespace_name} contains invalid symbol {symbol!r}")
            if symbol in symbols:
                raise RegistryError(
                    "duplicate_symbol", f"symbol {symbol} is declared more than once",
                    first_namespace=symbols[symbol][0], second_namespace=namespace_name,
                )
            if not isinstance(numeric_id, int) or not numeric_min <= numeric_id <= numeric_max:
                raise RegistryError("invalid_numeric_id", f"resource {symbol} has an out-of-range numeric ID")
            if access not in ("write", "read_only"):
                raise RegistryError("invalid_access", f"resource {symbol} has invalid access {access!r}")
            classification, _evidence = _slot_classification(namespace, numeric_id)
            if access == "write" and classification not in WRITABLE_CLASSIFICATIONS:
                raise RegistryError(
                    f"{classification.lower()}_id",
                    f"writable resource {symbol} cannot own {classification} ID {numeric_id}",
                    namespace=namespace_name, numeric_id=numeric_id,
                )
            if access == "read_only" and classification not in {"VANILLA_OWNED", "CONTROLLED_REPLACEMENT"}:
                raise RegistryError(
                    "invalid_read_only_reference",
                    f"read-only resource {symbol} must identify source-backed vanilla or controlled data",
                )
            owner_key = (collision_domain, numeric_id)
            if access == "write" and owner_key in numeric_owners:
                first_namespace, first_symbol = numeric_owners[owner_key]
                raise RegistryError(
                    "duplicate_numeric_ownership",
                    f"numeric ID {numeric_id} in collision domain {collision_domain} has multiple owners",
                    first=f"{first_namespace}:{first_symbol}", second=f"{namespace_name}:{symbol}",
                )
            if access == "write":
                numeric_owners[owner_key] = (namespace_name, symbol)
            symbols[symbol] = (namespace_name, resource)

    for collision_domain, append in append_domains.items():
        appended_ids = sorted(
            resource["id"]
            for namespace in namespaces.values()
            if namespace["collision_domain"] == collision_domain
            for resource in namespace.get("resources", [])
            if resource.get("access", "write") == "write"
            and _slot_classification(namespace, resource["id"])[0] == "PROJECT_APPENDED"
        )
        if appended_ids:
            expected = list(range(append["allocation_start"], appended_ids[-1] + 1))
            if appended_ids != expected:
                raise RegistryError(
                    "append_gap",
                    f"collision domain {collision_domain} has a gap in persistent appended ownership",
                    expected=expected, actual=appended_ids,
                )
    header_namespace = namespaces.get("map_headers", {})
    header_expansion = header_namespace.get("header_expansion")
    if header_expansion is not None:
        project_ids = sorted(
            resource["id"] for resource in header_namespace.get("resources", [])
            if resource.get("access", "write") == "write"
            and _slot_classification(header_namespace, resource["id"])[0] == "PROJECT_HEADER"
        )
        if project_ids:
            expected = list(range(header_expansion["allocation_start"], project_ids[-1] + 1))
            if project_ids != expected:
                raise RegistryError("header_expansion_gap", "project map-header ownership must remain contiguous", expected=expected, actual=project_ids)
    return registry


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    return validate_registry(_load_json(path))


def resolve_symbol(
    registry: dict[str, Any],
    symbol: str,
    expected_namespace: str | None = None,
    *,
    require_writable: bool = True,
) -> dict[str, Any]:
    if not isinstance(symbol, str):
        raise RegistryError("numeric_reference", "registry-owned references must be symbolic strings")
    matches: list[tuple[str, dict[str, Any]]] = []
    for namespace_name, namespace in registry["namespaces"].items():
        for resource in namespace.get("resources", []):
            if resource["symbol"] == symbol:
                matches.append((namespace_name, resource))
    if not matches:
        raise RegistryError("unknown_reference", f"unknown registry symbol {symbol!r}")
    namespace_name, resource = matches[0]
    if expected_namespace is not None and namespace_name != expected_namespace:
        raise RegistryError(
            "wrong_namespace",
            f"symbol {symbol!r} belongs to {namespace_name}, not {expected_namespace}",
            symbol=symbol, actual_namespace=namespace_name, expected_namespace=expected_namespace,
        )
    if require_writable and resource.get("access", "write") != "write":
        raise RegistryError("read_only_reference", f"symbol {symbol!r} is read-only")
    classification, evidence = _slot_classification(registry["namespaces"][namespace_name], resource["id"])
    return {
        "symbol": symbol,
        "namespace": namespace_name,
        "id": resource["id"],
        "classification": classification,
        "access": resource.get("access", "write"),
        "evidence": evidence.get("evidence"),
    }


def resolve_world_source(
    source: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Resolve the bounded symbolic Stage 3C source into the Stage 3B IR."""
    if source.get("schema_version") != 4 or source.get("artifact_namespace") != "stage3c":
        raise RegistryError("unsupported_world_schema", "symbolic world source must use Stage 3C schema 4")
    registry = load_registry(registry_path)
    declared_registry = source.get("registry")
    try:
        declared_path = (PROJECT_ROOT / declared_registry).resolve() if isinstance(declared_registry, str) else None
    except OSError as error:
        raise RegistryError("invalid_registry_reference", "world registry path is invalid") from error
    if declared_path != registry_path.resolve():
        raise RegistryError("registry_mismatch", "world source must name the registry used for resolution")

    resolutions: dict[str, dict[str, Any]] = {}

    def resolve(reference: object, namespace: str, *, writable: bool = True) -> int:
        if not isinstance(reference, str):
            raise RegistryError(
                "numeric_reference",
                f"Stage 3C {namespace} references must be symbolic strings, got {reference!r}",
                namespace=namespace,
            )
        result = resolve_symbol(registry, reference, namespace, require_writable=writable)
        resolutions[reference] = result
        return int(result["id"])

    matrix = source.get("world", {}).get("matrix", {})
    matrix_symbol = matrix.get("id")
    matrix_id = resolve(matrix_symbol, "matrices")
    if matrix.get("width") != 2 or matrix.get("height") != 2:
        raise RegistryError("invalid_matrix_dimensions", "Stage 3C proof matrix must be exactly 2x2")
    cells = matrix.get("cells")
    if not isinstance(cells, list) or len(cells) != 4 or len(set(cells)) != 4:
        raise RegistryError("invalid_matrix_cells", "Stage 3C matrix needs four unique symbolic map cells")
    maps = source.get("maps")
    if not isinstance(maps, dict) or set(maps) != set(cells):
        raise RegistryError("dangling_map", "matrix cells and declared symbolic maps must match exactly")

    shared = source.get("resources")
    expected_shared = {
        "event_bank": "event_banks",
        "local_script_bank": "local_script_banks",
        "start_script": "common_scripts",
        "script_header": "script_headers",
        "text_bank": "text_banks",
    }
    if not isinstance(shared, dict) or set(shared) != set(expected_shared):
        raise RegistryError("invalid_shared_resources", "Stage 3C shared resource references are incomplete")
    shared_ids = {key: resolve(shared[key], namespace) for key, namespace in expected_shared.items()}

    aliases_by_cell = {(0, 0): "nw", (0, 1): "ne", (1, 0): "sw", (1, 1): "se"}
    aliases_by_symbol: dict[str, str] = {}
    resolved_maps: dict[str, Any] = {}
    required_map_fields = {
        "cell", "matrix", "map_header", "map_member", "event_bank", "script_bank",
        "script_header", "text_bank", "edge_openings", "identity_blocked_tile",
    }
    for map_symbol in cells:
        map_spec = maps[map_symbol]
        if not isinstance(map_spec, dict) or set(map_spec) != required_map_fields:
            raise RegistryError("invalid_map", f"symbolic map {map_symbol!r} has unsupported or missing fields")
        cell = map_spec["cell"]
        if not isinstance(cell, dict) or set(cell) != {"row", "column"}:
            raise RegistryError("invalid_map_cell", f"map {map_symbol!r} has a malformed cell")
        alias = aliases_by_cell.get((cell["row"], cell["column"]))
        if alias is None or alias in resolved_maps:
            raise RegistryError("invalid_map_cell", f"map {map_symbol!r} has an impossible or duplicate cell")
        aliases_by_symbol[map_symbol] = alias
        if map_spec["matrix"] != matrix_symbol:
            raise RegistryError("wrong_matrix_reference", f"map {map_symbol!r} points at the wrong matrix")
        resolve(map_spec["matrix"], "matrices")
        per_map_shared = {
            "event_bank": ("event_bank", "event_banks"),
            "script_bank": ("local_script_bank", "local_script_banks"),
            "script_header": ("script_header", "script_headers"),
            "text_bank": ("text_bank", "text_banks"),
        }
        for map_key, (shared_key, namespace) in per_map_shared.items():
            if map_spec[map_key] != shared[shared_key]:
                raise RegistryError(
                    "inconsistent_dependency",
                    f"map {map_symbol!r} {map_key} disagrees with the bounded shared bank",
                )
            resolve(map_spec[map_key], namespace)
        resolved_maps[alias] = {
            "cell": copy.deepcopy(cell),
            "map_header": resolve(map_spec["map_header"], "map_headers"),
            "map_member": resolve(map_spec["map_member"], "map_members"),
            "edge_openings": copy.deepcopy(map_spec["edge_openings"]),
            "identity_blocked_tile": copy.deepcopy(map_spec["identity_blocked_tile"]),
        }

    if [aliases_by_symbol[symbol] for symbol in cells] != ["nw", "ne", "sw", "se"]:
        raise RegistryError("invalid_matrix_order", "Stage 3C matrix cells must be row-major by declared coordinates")
    player_start = copy.deepcopy(source.get("player_start", {}))
    if player_start.get("map") not in aliases_by_symbol:
        raise RegistryError("unknown_reference", "player start refers to an undeclared symbolic map")
    player_start["map"] = aliases_by_symbol[player_start["map"]]

    model = copy.deepcopy(source.get("model", {}))
    model["template_map_member"] = resolve(model.get("template_map_member"), "map_members", writable=False)
    model["area_data"] = resolve(model.get("area_data"), "area_data_banks", writable=False)
    header_template = resolve(source.get("header_template"), "map_headers", writable=False)

    resolved_matrix = copy.deepcopy(matrix)
    del resolved_matrix["id"]
    resolved_matrix["cells"] = [aliases_by_symbol[symbol] for symbol in cells]
    registry_hash = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    return {
        "schema_version": 3,
        "canonical_schema_version": 4,
        "id": source.get("id"),
        "artifact_namespace": "stage3c",
        "dimensions": copy.deepcopy(source.get("dimensions")),
        "world": {"matrix": resolved_matrix},
        "maps": resolved_maps,
        "slots": {
            "matrix": matrix_id,
            "event": shared_ids["event_bank"],
            "script": shared_ids["local_script_bank"],
            "start_script": shared_ids["start_script"],
            "script_header": shared_ids["script_header"],
            "text": shared_ids["text_bank"],
        },
        "model": model,
        "terrain": copy.deepcopy(source.get("terrain")),
        "player_start": player_start,
        "warps": copy.deepcopy(source.get("warps")),
        "text": source.get("text"),
        "header_template": header_template,
        "registry_resolution": {
            "schema_version": 1,
            "registry": declared_registry,
            "registry_sha256": registry_hash,
            "target_rom_sha256": registry["target"]["rom_sha256"],
            "symbols": {symbol: resolutions[symbol] for symbol in sorted(resolutions)},
        },
    }


def resolve_stage3d_source(
    source: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Resolve the symbolic single-map Stage 3D source into serializer inputs."""
    if source.get("schema_version") != 5 or source.get("artifact_namespace") != "stage3d":
        raise RegistryError("unsupported_world_schema", "Stage 3D symbolic terrain source must use schema 5")
    registry = load_registry(registry_path)
    declared_registry = source.get("registry")
    declared_path = (PROJECT_ROOT / declared_registry).resolve() if isinstance(declared_registry, str) else None
    if declared_path != registry_path.resolve():
        raise RegistryError("registry_mismatch", "Stage 3D world source must name the registry used for resolution")

    resolutions: dict[str, dict[str, Any]] = {}

    def resolve(reference: object, namespace: str, *, writable: bool = True) -> int:
        if not isinstance(reference, str):
            raise RegistryError(
                "numeric_reference", f"Stage 3D {namespace} references must be symbolic strings",
                namespace=namespace, value=reference,
            )
        result = resolve_symbol(registry, reference, namespace, require_writable=writable)
        resolutions[reference] = result
        return int(result["id"])

    matrix = source.get("world", {}).get("matrix", {})
    if not isinstance(matrix, dict) or set(matrix) != {"id", "width", "height", "name", "cells", "altitudes"}:
        raise RegistryError("invalid_matrix", "Stage 3D requires one exact symbolic matrix declaration")
    if matrix["width"] != 1 or matrix["height"] != 1 or len(matrix["cells"]) != 1 or matrix["altitudes"] != [0]:
        raise RegistryError("invalid_matrix_dimensions", "Stage 3D geometry proof requires one 1x1 matrix")
    matrix_id = resolve(matrix["id"], "matrices")

    map_spec = source.get("map")
    required_map = {
        "id", "matrix", "map_header", "map_member", "event_bank", "script_bank", "script_header", "text_bank",
    }
    if not isinstance(map_spec, dict) or set(map_spec) != required_map:
        raise RegistryError("invalid_map", "Stage 3D symbolic map has unsupported or missing fields")
    if matrix["cells"] != [map_spec["id"]]:
        raise RegistryError("dangling_map", "Stage 3D matrix cell must reference the declared local map")
    if map_spec["matrix"] != matrix["id"]:
        raise RegistryError("wrong_matrix_reference", "Stage 3D map points at the wrong matrix")

    shared = source.get("resources")
    expected_shared = {
        "event_bank": "event_banks", "local_script_bank": "local_script_banks",
        "start_script": "common_scripts", "script_header": "script_headers", "text_bank": "text_banks",
    }
    if not isinstance(shared, dict) or set(shared) != set(expected_shared):
        raise RegistryError("invalid_shared_resources", "Stage 3D shared symbolic resources are incomplete")
    shared_ids = {name: resolve(shared[name], namespace) for name, namespace in expected_shared.items()}
    dependencies = {
        "event_bank": ("event_bank", "event_banks"),
        "script_bank": ("local_script_bank", "local_script_banks"),
        "script_header": ("script_header", "script_headers"),
        "text_bank": ("text_bank", "text_banks"),
    }
    for map_key, (shared_key, namespace) in dependencies.items():
        if map_spec[map_key] != shared[shared_key]:
            raise RegistryError("inconsistent_dependency", f"Stage 3D map {map_key} disagrees with shared resources")
        resolve(map_spec[map_key], namespace)

    model = copy.deepcopy(source.get("model", {}))
    model["template_map_member"] = resolve(model.get("template_map_member"), "map_members", writable=False)
    model["area_data"] = resolve(model.get("area_data"), "area_data_banks", writable=False)
    header_template = resolve(source.get("header_template"), "map_headers", writable=False)
    player_start = copy.deepcopy(source.get("player_start", {}))
    if player_start.get("map") != map_spec["id"]:
        raise RegistryError("unknown_reference", "Stage 3D player start must reference its declared local map")
    player_start.pop("map")

    return {
        "schema_version": 5,
        "canonical_schema_version": 5,
        "id": source.get("id"),
        "artifact_namespace": "stage3d",
        "dimensions": copy.deepcopy(source.get("dimensions")),
        "world": {"matrix": {
            "width": 1, "height": 1, "name": matrix["name"], "altitudes": [0],
        }},
        "slots": {
            "matrix": matrix_id,
            "map_header": resolve(map_spec["map_header"], "map_headers"),
            "map_member": resolve(map_spec["map_member"], "map_members"),
            "event": shared_ids["event_bank"],
            "script": shared_ids["local_script_bank"],
            "start_script": shared_ids["start_script"],
            "script_header": shared_ids["script_header"],
            "text": shared_ids["text_bank"],
        },
        "model": model,
        "geometry": copy.deepcopy(source.get("geometry")),
        "player_start": player_start,
        "warps": copy.deepcopy(source.get("warps")),
        "text": source.get("text"),
        "header_template": header_template,
        "registry_resolution": {
            "schema_version": 1,
            "registry": declared_registry,
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "target_rom_sha256": registry["target"]["rom_sha256"],
            "symbols": {symbol: resolutions[symbol] for symbol in sorted(resolutions)},
        },
    }


def resolve_stage4b_source(
    source: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Resolve the symbolic single-map Stage 4B asset proof into serializer inputs."""
    if source.get("schema_version") != 8 or source.get("artifact_namespace") != "stage4b":
        raise RegistryError("unsupported_world_schema", "Stage 4B symbolic asset source must use schema 8")
    registry = load_registry(registry_path)
    declared_registry = source.get("registry")
    declared_path = (PROJECT_ROOT / declared_registry).resolve() if isinstance(declared_registry, str) else None
    if declared_path != registry_path.resolve():
        raise RegistryError("registry_mismatch", "Stage 4B world source must name the registry used for resolution")

    resolutions: dict[str, dict[str, Any]] = {}

    def resolve(reference: object, namespace: str, *, writable: bool = True) -> int:
        if not isinstance(reference, str):
            raise RegistryError(
                "numeric_reference", f"Stage 4B {namespace} references must be symbolic strings",
                namespace=namespace, value=reference,
            )
        result = resolve_symbol(registry, reference, namespace, require_writable=writable)
        resolutions[reference] = result
        return int(result["id"])

    matrix = source.get("world", {}).get("matrix", {})
    if not isinstance(matrix, dict) or set(matrix) != {"id", "width", "height", "name", "cells", "altitudes"}:
        raise RegistryError("invalid_matrix", "Stage 4B requires one exact symbolic matrix declaration")
    if matrix["width"] != 1 or matrix["height"] != 1 or len(matrix["cells"]) != 1 or matrix["altitudes"] != [0]:
        raise RegistryError("invalid_matrix_dimensions", "Stage 4B asset proof requires one 1x1 matrix")
    matrix_id = resolve(matrix["id"], "matrices")

    map_spec = source.get("map")
    required_map = {
        "id", "matrix", "map_header", "map_member", "event_bank", "script_bank", "script_header", "text_bank",
    }
    if not isinstance(map_spec, dict) or set(map_spec) != required_map:
        raise RegistryError("invalid_map", "Stage 4B symbolic map has unsupported or missing fields")
    if matrix["cells"] != [map_spec["id"]]:
        raise RegistryError("dangling_map", "Stage 4B matrix cell must reference the declared local map")
    if map_spec["matrix"] != matrix["id"]:
        raise RegistryError("wrong_matrix_reference", "Stage 4B map points at the wrong matrix")

    shared = source.get("resources")
    expected_shared = {
        "event_bank": "event_banks", "local_script_bank": "local_script_banks",
        "start_script": "common_scripts", "script_header": "script_headers", "text_bank": "text_banks",
    }
    if not isinstance(shared, dict) or set(shared) != set(expected_shared):
        raise RegistryError("invalid_shared_resources", "Stage 4B shared symbolic resources are incomplete")
    shared_ids = {name: resolve(shared[name], namespace) for name, namespace in expected_shared.items()}
    dependencies = {
        "event_bank": ("event_bank", "event_banks"),
        "script_bank": ("local_script_bank", "local_script_banks"),
        "script_header": ("script_header", "script_headers"),
        "text_bank": ("text_bank", "text_banks"),
    }
    for map_key, (shared_key, namespace) in dependencies.items():
        if map_spec[map_key] != shared[shared_key]:
            raise RegistryError("inconsistent_dependency", f"Stage 4B map {map_key} disagrees with shared resources")
        resolve(map_spec[map_key], namespace)

    model = copy.deepcopy(source.get("model", {}))
    model["template_map_member"] = resolve(model.get("template_map_member"), "map_members", writable=False)
    model["area_data"] = resolve(model.get("area_data"), "area_data_banks", writable=False)
    header_template = resolve(source.get("header_template"), "map_headers", writable=False)
    player_start = copy.deepcopy(source.get("player_start", {}))
    if player_start.get("map") != map_spec["id"]:
        raise RegistryError("unknown_reference", "Stage 4B player start must reference its declared local map")
    player_start.pop("map")

    return {
        "schema_version": 8,
        "canonical_schema_version": 8,
        "id": source.get("id"),
        "artifact_namespace": "stage4b",
        "dimensions": copy.deepcopy(source.get("dimensions")),
        "world": {"matrix": {
            "width": 1, "height": 1, "name": matrix["name"], "altitudes": [0],
        }},
        "slots": {
            "matrix": matrix_id,
            "map_header": resolve(map_spec["map_header"], "map_headers"),
            "map_member": resolve(map_spec["map_member"], "map_members"),
            "event": shared_ids["event_bank"],
            "script": shared_ids["local_script_bank"],
            "start_script": shared_ids["start_script"],
            "script_header": shared_ids["script_header"],
            "text": shared_ids["text_bank"],
        },
        "model": model,
        "terrain": copy.deepcopy(source.get("terrain")),
        "asset_catalog": source.get("asset_catalog"),
        "assets": copy.deepcopy(source.get("assets")),
        "player_start": player_start,
        "warps": copy.deepcopy(source.get("warps")),
        "text": source.get("text"),
        "header_template": header_template,
        "registry_resolution": {
            "schema_version": 1,
            "registry": declared_registry,
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "target_rom_sha256": registry["target"]["rom_sha256"],
            "symbols": {symbol: resolutions[symbol] for symbol in sorted(resolutions)},
        },
    }


def resolve_stage4c_source(
    source: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Resolve Stage 4C through the unchanged Stage 4B symbolic world graph."""
    if source.get("schema_version") != 9 or source.get("artifact_namespace") != "stage4c":
        raise RegistryError("unsupported_world_schema", "Stage 4C symbolic texture source must use schema 9")
    stage4b_view = copy.deepcopy(source)
    stage4b_view["schema_version"] = 8
    stage4b_view["artifact_namespace"] = "stage4b"
    resolved = resolve_stage4b_source(stage4b_view, registry_path)
    resolved["schema_version"] = 9
    resolved["canonical_schema_version"] = 9
    resolved["artifact_namespace"] = "stage4c"
    return resolved


def resolve_stage3e1_source(
    source: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Resolve the symbolic two-cell NARC-append proof into serializer inputs."""
    schema_version = source.get("schema_version")
    namespace = source.get("artifact_namespace")
    if (schema_version, namespace) not in ((6, "stage3e1"), (7, "stage3e2")):
        raise RegistryError("unsupported_world_schema", "symbolic append/header source must use Stage 3E1 schema 6 or Stage 3E2 schema 7")
    stage = "Stage 3E2" if schema_version == 7 else "Stage 3E1"
    registry = load_registry(registry_path)
    declared_registry = source.get("registry")
    declared_path = (PROJECT_ROOT / declared_registry).resolve() if isinstance(declared_registry, str) else None
    if declared_path != registry_path.resolve():
        raise RegistryError("registry_mismatch", "Stage 3E1 source must name the registry used for resolution")
    resolutions: dict[str, dict[str, Any]] = {}

    def resolve(reference: object, namespace: str, *, writable: bool = True) -> int:
        if not isinstance(reference, str):
            raise RegistryError(
                "numeric_reference", f"{stage} {namespace} references must be symbolic strings",
                namespace=namespace, value=reference,
            )
        result = resolve_symbol(registry, reference, namespace, require_writable=writable)
        resolutions[reference] = result
        return int(result["id"])

    matrix = source.get("world", {}).get("matrix", {})
    required_matrix = {
        "id", "append_probe", "width", "height", "name", "cells", "altitudes", "external_boundaries",
    }
    if not isinstance(matrix, dict) or set(matrix) != required_matrix:
        raise RegistryError("invalid_matrix", f"{stage} requires one exact symbolic matrix declaration")
    if matrix["width"] != 2 or matrix["height"] != 1 or matrix["altitudes"] != [0, 0]:
        raise RegistryError("invalid_matrix_dimensions", f"{stage} proof matrix must be exactly 2x1")
    cells = matrix["cells"]
    if not isinstance(cells, list) or len(cells) != 2 or len(set(cells)) != 2:
        raise RegistryError("invalid_matrix_cells", f"{stage} matrix needs two unique map cells")
    matrix_id = resolve(matrix["id"], "matrices")
    matrix_probe_id = resolve(matrix["append_probe"], "matrices")
    if matrix_probe_id != matrix_id + 1:
        raise RegistryError("append_gap", f"{stage} matrix probe must immediately follow the active matrix")

    maps = source.get("maps")
    if not isinstance(maps, dict) or set(maps) != set(cells):
        raise RegistryError("dangling_map", f"{stage} matrix cells and maps must match")
    aliases_by_cell = {(0, 0): "west", (0, 1): "east"}
    aliases_by_symbol: dict[str, str] = {}
    resolved_maps: dict[str, dict[str, Any]] = {}
    required_map = {
        "cell", "matrix", "map_header", "map_member", "event_bank", "script_bank",
        "script_header", "text_bank", "edge_openings", "identity_blocked_tile", "npc",
    }
    for map_symbol in cells:
        map_spec = maps[map_symbol]
        if not isinstance(map_spec, dict) or set(map_spec) != required_map:
            raise RegistryError("invalid_map", f"{stage} map {map_symbol!r} has unsupported fields")
        cell = map_spec["cell"]
        if not isinstance(cell, dict) or set(cell) != {"row", "column"}:
            raise RegistryError("invalid_map_cell", f"{stage} map {map_symbol!r} has malformed coordinates")
        alias = aliases_by_cell.get((cell["row"], cell["column"]))
        if alias is None or alias in resolved_maps:
            raise RegistryError("invalid_map_cell", f"{stage} map {map_symbol!r} has duplicate/impossible coordinates")
        if map_spec["matrix"] != matrix["id"]:
            raise RegistryError("wrong_matrix_reference", f"{stage} map {map_symbol!r} points at the wrong matrix")
        resolve(map_spec["matrix"], "matrices")
        aliases_by_symbol[map_symbol] = alias
        npc = copy.deepcopy(map_spec["npc"])
        marker_symbol = npc.get("marker_variable")
        npc["marker_var"] = resolve(marker_symbol, "variables")
        npc.pop("marker_variable", None)
        resolved_maps[alias] = {
            "cell": copy.deepcopy(cell),
            "map_header": resolve(map_spec["map_header"], "map_headers"),
            "map_member": resolve(map_spec["map_member"], "map_members"),
            "event": resolve(map_spec["event_bank"], "event_banks"),
            "script": resolve(map_spec["script_bank"], "local_script_banks"),
            "script_header": resolve(map_spec["script_header"], "script_headers"),
            "text": resolve(map_spec["text_bank"], "text_banks"),
            "edge_openings": copy.deepcopy(map_spec["edge_openings"]),
            "identity_blocked_tile": copy.deepcopy(map_spec["identity_blocked_tile"]),
            "npc": npc,
        }
    if [aliases_by_symbol[symbol] for symbol in cells] != ["west", "east"]:
        raise RegistryError("invalid_matrix_order", f"{stage} cells must be row-major west then east")

    model = copy.deepcopy(source.get("model", {}))
    model["template_map_member"] = resolve(model.get("template_map_member"), "map_members", writable=False)
    model["area_data"] = resolve(model.get("area_data"), "area_data_banks", writable=False)
    header_template = resolve(source.get("header_template"), "map_headers", writable=False)
    start_script = resolve(source.get("resources", {}).get("start_script"), "common_scripts")
    start = copy.deepcopy(source.get("player_start", {}))
    if start.get("map") not in aliases_by_symbol:
        raise RegistryError("unknown_reference", f"{stage} player start references an undeclared map")
    start["map"] = aliases_by_symbol[start["map"]]

    resolved_matrix = copy.deepcopy(matrix)
    for key in ("id", "append_probe"):
        del resolved_matrix[key]
    resolved_matrix["cells"] = [aliases_by_symbol[symbol] for symbol in cells]
    resolved_warps = []
    for warp in source.get("warps", []):
        if not isinstance(warp, dict) or set(warp) != {"map", "local_x", "local_z", "destination_map", "destination_warp"}:
            raise RegistryError("invalid_warp", f"{stage} contains a malformed warp")
        if warp["map"] not in aliases_by_symbol or warp["destination_map"] not in aliases_by_symbol:
            raise RegistryError("unknown_reference", f"{stage} warp references an undeclared map")
        resolved_warps.append({
            "map": aliases_by_symbol[warp["map"]],
            "local_x": warp["local_x"],
            "local_z": warp["local_z"],
            "destination_header": resolved_maps[aliases_by_symbol[warp["destination_map"]]]["map_header"],
            "destination_warp": warp["destination_warp"],
        })
    if schema_version == 7:
        header_ids = [resolved_maps[name]["map_header"] for name in ("west", "east")]
        if header_ids != [540, 541]:
            raise RegistryError("invalid_project_header", "Stage 3E2 must own contiguous project headers 540 and 541")
        for map_symbol in cells:
            result = resolutions[maps[map_symbol]["map_header"]]
            if result["classification"] != "PROJECT_HEADER":
                raise RegistryError("invalid_project_header", "Stage 3E2 map headers must resolve to PROJECT_HEADER ownership")
    return {
        "schema_version": schema_version,
        "canonical_schema_version": schema_version,
        "id": source.get("id"),
        "artifact_namespace": namespace,
        "dimensions": copy.deepcopy(source.get("dimensions")),
        "world": {"matrix": resolved_matrix},
        "maps": resolved_maps,
        "slots": {"matrix": matrix_id, "matrix_probe": matrix_probe_id, "start_script": start_script},
        "model": model,
        "terrain": copy.deepcopy(source.get("terrain")),
        "player_start": start,
        "warps": resolved_warps,
        "header_profile": copy.deepcopy(source.get("header_profile")) if schema_version == 7 else None,
        "header_template": header_template,
        "registry_resolution": {
            "schema_version": 1,
            "registry": declared_registry,
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "target_rom_sha256": registry["target"]["rom_sha256"],
            "symbols": {symbol: resolutions[symbol] for symbol in sorted(resolutions)},
        },
    }


def allocate_resource(
    registry: dict[str, Any],
    namespace_name: str,
    symbol: str,
    pinned_id: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copy with one persistent allocation; never renumber records."""
    registry = copy.deepcopy(validate_registry(registry))
    if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
        raise RegistryError("invalid_symbol", f"invalid allocation symbol {symbol!r}")
    try:
        resolve_symbol(registry, symbol, require_writable=False)
    except RegistryError as error:
        if error.code != "unknown_reference":
            raise
    else:
        raise RegistryError("duplicate_symbol", f"symbol {symbol} already exists")
    if namespace_name not in registry["namespaces"]:
        raise RegistryError("unknown_namespace", f"unknown namespace {namespace_name!r}")
    namespace = registry["namespaces"][namespace_name]
    domain = namespace["collision_domain"]
    occupied = {
        resource["id"]
        for other in registry["namespaces"].values()
        if other["collision_domain"] == domain
        for resource in other.get("resources", [])
        if resource.get("access", "write") == "write"
    }
    candidates = [
        numeric_id
        for range_spec in namespace.get("ranges", [])
        if range_spec["classification"] == "KNOWN_FREE"
        for numeric_id in range(range_spec["start"], range_spec["end"] + 1)
    ]
    if pinned_id is not None:
        if not isinstance(pinned_id, int) or pinned_id not in candidates:
            classification = (
                _slot_classification(namespace, pinned_id)[0]
                if isinstance(pinned_id, int) and namespace["numeric_min"] <= pinned_id <= namespace["numeric_max"]
                else "OUT_OF_RANGE"
            )
            raise RegistryError(
                "invalid_manual_pin",
                f"manual pin {pinned_id!r} is not in a KNOWN_FREE range",
                classification=classification,
            )
        candidates = [pinned_id]
    numeric_id = next((candidate for candidate in candidates if candidate not in occupied), None)
    if numeric_id is None:
        raise RegistryError("allocation_exhausted", f"no KNOWN_FREE IDs remain in namespace {namespace_name}")
    namespace.setdefault("slot_overrides", {})[str(numeric_id)] = {
        "classification": "PROJECT_ALLOCATED",
        "evidence": "persistent allocation from a registry KNOWN_FREE range",
    }
    resource = {"symbol": symbol, "id": numeric_id, "access": "write"}
    namespace.setdefault("resources", []).append(resource)
    namespace["resources"].sort(key=lambda item: item["symbol"])
    validate_registry(registry)
    return registry, resolve_symbol(registry, symbol, namespace_name)


def allocate_appended_resource(
    registry: dict[str, Any],
    namespace_name: str,
    symbol: str,
    rom_path: Path,
    pinned_id: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist one contiguous member in a revision-locked, append-proven NARC window."""
    registry = copy.deepcopy(validate_registry(registry))
    verify_rom_revision(registry, rom_path)
    if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
        raise RegistryError("invalid_symbol", f"invalid allocation symbol {symbol!r}")
    try:
        resolve_symbol(registry, symbol, require_writable=False)
    except RegistryError as error:
        if error.code != "unknown_reference":
            raise
    else:
        raise RegistryError("duplicate_symbol", f"symbol {symbol} already exists")
    namespace = registry.get("namespaces", {}).get(namespace_name)
    if namespace is None:
        raise RegistryError("unknown_namespace", f"unknown namespace {namespace_name!r}")
    append = namespace.get("append")
    if append is None:
        raise RegistryError("unproven_append", f"namespace {namespace_name} has no append-proven window")

    collision_domain = namespace["collision_domain"]
    occupied = {
        resource["id"]
        for other in registry["namespaces"].values()
        if other["collision_domain"] == collision_domain
        for resource in other.get("resources", [])
        if resource.get("access", "write") == "write"
    }
    pristine_count = append["pristine_count"]
    allocation_start = append["allocation_start"]
    next_id = allocation_start
    while next_id in occupied:
        next_id += 1
    if pinned_id is not None:
        if not isinstance(pinned_id, int):
            raise RegistryError("invalid_append_pin", "appended manual pins must be integers")
        if pinned_id < allocation_start:
            raise RegistryError(
                "append_below_pristine",
                f"appended ID {pinned_id} is below allocation boundary {allocation_start} "
                f"(retail count {pristine_count})",
            )
        if pinned_id != next_id:
            raise RegistryError(
                "noncontiguous_append_pin",
                f"appended manual pin {pinned_id} would skip or collide with the next ID {next_id}",
            )
    numeric_id = next_id if pinned_id is None else pinned_id
    if numeric_id > append["proven_max_id"]:
        raise RegistryError(
            "append_allocation_exhausted",
            f"append-proven window is exhausted in namespace {namespace_name}",
        )
    if _range_classification(namespace, numeric_id)[0] != "APPEND_PROVEN":
        raise RegistryError("unproven_append", f"ID {numeric_id} is not in an APPEND_PROVEN range")
    namespace.setdefault("slot_overrides", {})[str(numeric_id)] = {
        "classification": "PROJECT_APPENDED",
        "evidence": "persistent contiguous allocation from the Stage 3E1 append-proven window",
    }
    namespace.setdefault("resources", []).append({
        "symbol": symbol, "id": numeric_id, "access": "write",
    })
    namespace["resources"].sort(key=lambda item: item["symbol"])
    validate_registry(registry)
    return registry, resolve_symbol(registry, symbol, namespace_name)


def allocate_project_header(
    registry: dict[str, Any],
    symbol: str,
    rom_path: Path,
    pinned_id: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist one contiguous, revision-locked map header beyond retail ID 539."""
    registry = copy.deepcopy(validate_registry(registry))
    verify_rom_revision(registry, rom_path)
    if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
        raise RegistryError("invalid_symbol", f"invalid allocation symbol {symbol!r}")
    try:
        resolve_symbol(registry, symbol, require_writable=False)
    except RegistryError as error:
        if error.code != "unknown_reference":
            raise
    else:
        raise RegistryError("duplicate_symbol", f"symbol {symbol} already exists")

    namespace = registry["namespaces"].get("map_headers")
    if namespace is None or namespace.get("header_expansion") is None:
        raise RegistryError("unproven_header_expansion", "map_headers has no expansion-proven window")
    expansion = namespace["header_expansion"]
    occupied = {
        resource["id"] for resource in namespace.get("resources", [])
        if resource.get("access", "write") == "write"
    }
    next_id = expansion["allocation_start"]
    while next_id in occupied:
        next_id += 1
    if pinned_id is not None:
        if not isinstance(pinned_id, int):
            raise RegistryError("invalid_header_pin", "project-header manual pins must be integers")
        if pinned_id < expansion["allocation_start"]:
            raise RegistryError(
                "header_below_expansion_boundary",
                f"project header {pinned_id} is below expansion boundary {expansion['allocation_start']}",
            )
        if pinned_id != next_id:
            raise RegistryError(
                "noncontiguous_header_pin",
                f"project-header pin {pinned_id} would skip or collide with next ID {next_id}",
            )
    numeric_id = next_id if pinned_id is None else pinned_id
    if numeric_id > expansion["proven_max_id"]:
        raise RegistryError(
            "header_allocation_exhausted",
            "map-header expansion-proven window is exhausted",
        )
    if _range_classification(namespace, numeric_id)[0] != "HEADER_EXPANSION_PROVEN":
        raise RegistryError(
            "unproven_header_expansion", f"ID {numeric_id} is outside the expansion-proven range",
        )
    namespace.setdefault("slot_overrides", {})[str(numeric_id)] = {
        "classification": "PROJECT_HEADER",
        "evidence": "persistent contiguous allocation from the Stage 3E2 expansion-proven window",
    }
    namespace.setdefault("resources", []).append({
        "symbol": symbol, "id": numeric_id, "access": "write",
    })
    namespace["resources"].sort(key=lambda item: item["symbol"])
    validate_registry(registry)
    return registry, resolve_symbol(registry, symbol, "map_headers")


def verify_rom_revision(registry: dict[str, Any], rom_path: Path) -> dict[str, Any]:
    if not rom_path.is_file():
        raise RegistryError("rom_missing", f"supported user-local ROM is missing: {rom_path}")
    data = rom_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rom = NintendoDSRom(data)
    game_code = bytes(rom.idCode).decode("ascii", errors="replace")
    target = registry["target"]
    if game_code != target["game_code"] or digest != target["rom_sha256"]:
        raise RegistryError(
            "unsupported_rom_revision",
            "registry allocation is coupled to the verified US HeartGold revision",
            expected_game_code=target["game_code"], actual_game_code=game_code,
            expected_sha256=target["rom_sha256"], actual_sha256=digest,
        )
    arm9_hash = hashlib.sha256(rom.arm9).hexdigest()
    if arm9_hash != target["arm9_sha256"]:
        raise RegistryError("unsupported_arm9_revision", "ROM ARM9 does not match registry target")
    return {"game_code": game_code, "rom_sha256": digest, "arm9_sha256": arm9_hash, "size_bytes": len(data)}


def build_inventory(registry: dict[str, Any], rom_path: Path) -> dict[str, Any]:
    revision = verify_rom_revision(registry, rom_path)
    rom = NintendoDSRom.fromFile(str(rom_path))
    archives: dict[str, Any] = {}
    for label, path in sorted(registry["target"].get("archives", {}).items()):
        data = rom.getFileByName(path["path"])
        digest = hashlib.sha256(data).hexdigest()
        members = len(NARC(data).files)
        if digest != path["sha256"] or members != path["members"]:
            raise RegistryError("archive_revision_mismatch", f"archive {label} does not match registry evidence")
        archives[label] = {"path": path["path"], "members": members, "sha256": digest, "size_bytes": len(data)}
    namespace_inventory: dict[str, Any] = {}
    for name, namespace in sorted(registry["namespaces"].items()):
        resources = []
        for resource in sorted(namespace.get("resources", []), key=lambda item: item["symbol"]):
            resolved = resolve_symbol(registry, resource["symbol"], name, require_writable=False)
            resources.append({key: resolved[key] for key in ("symbol", "id", "classification", "access")})
        namespace_inventory[name] = {
            "storage": namespace["storage"],
            "collision_domain": namespace["collision_domain"],
            "allocation_policy": namespace["allocation_policy"],
            "append": copy.deepcopy(namespace.get("append")),
            "resources": resources,
            "classification_counts": {
                classification: sum(1 for resource in resources if resource["classification"] == classification)
                for classification in sorted(CLASSIFICATIONS)
            },
        }
    return {
        "schema_version": 1,
        "target": revision,
        "archives": archives,
        "namespaces": namespace_inventory,
        "notice": "Metadata and hashes only; no ROM member bytes are included.",
    }


def write_inventory(
    registry_path: Path = DEFAULT_REGISTRY,
    rom_path: Path = PROJECT_ROOT / "rom.nds",
    output_path: Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    inventory = build_inventory(registry, rom_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"success": True, "registry": str(registry_path), "output": str(output_path), "inventory": inventory}
