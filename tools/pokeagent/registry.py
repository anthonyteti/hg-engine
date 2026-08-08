"""Stable symbolic resource registry for the deterministic world compiler.

The registry intentionally separates numeric slot provenance from binary
serialization.  Existing allocations are persistent records; new allocations
may only consume ranges explicitly classified KNOWN_FREE.
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
    "KNOWN_FREE",
    "CONTROLLED_REPLACEMENT",
    "PROJECT_ALLOCATED",
    "VANILLA_OWNED",
    "RESERVED",
    "UNKNOWN",
}
WRITABLE_CLASSIFICATIONS = {"KNOWN_FREE", "CONTROLLED_REPLACEMENT", "PROJECT_ALLOCATED"}
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
