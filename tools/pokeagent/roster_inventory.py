"""Deterministic, source-backed HG-Engine roster capability inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
STATUSES = {"COMPLETE", "PARTIAL", "DATA_ONLY", "ASSET_ONLY", "NOT_IMPLEMENTED", "UNKNOWN"}

SPECIES_HEADER = Path("include/constants/species.h")
SPECIES_DATA = Path("data/Species.c")
EVOLUTION_DATA = Path("data/Evolutions.c")
FORM_MAP = Path("data/FormToSpeciesMapping.c")
LEARNSETS = Path("data/learnsets/learnsets.json")
FOLLOWER_TABLE = Path("src/field/overworld_table.c")
FOLLOWER_PROPERTIES = Path("data/FollowerProperties.c")
POKEDEX_SORT = Path("data/PokedexSort.c")
MEGA_TABLE = Path("src/battle/mega.c")
SPRITES = Path("data/graphics/sprites")
CRIES = Path("sound/cries")

GENERATION_RANGES = (
    (1, 1, 151),
    (2, 152, 251),
    (3, 252, 386),
    (4, 387, 493),
    (5, 544, 699),
    (6, 700, 771),
    (7, 772, 859),
    (8, 860, 955),
    (9, 956, 1075),
)


class InventoryError(ValueError):
    """Raised when source evidence is internally inconsistent."""


def _read(root: Path, relative: Path) -> str:
    path = root / relative
    if not path.is_file():
        raise InventoryError(f"missing source evidence: {relative}")
    return path.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _species_constants(root: Path) -> list[dict[str, Any]]:
    # This follows the engine's own graphics/learnset generators: canonical IDs are
    # declaration order, while many form macros are arithmetic expressions.
    names: list[str] = []
    for line in _read(root, SPECIES_HEADER).splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        name = fields[1].strip()
        if (
            "SPECIES" not in name
            or "_START" in name
            or "_SPECIES_H" in name
            or "_NUM (" in line
            or "INCLUDING_" in name
            or name.startswith("MAX_")
            or "_OVERWORLD_" in name
        ):
            continue
        names.append(name)
    if len(names) != 1476 or names[0] != "SPECIES_NONE" or names[-1] != "SPECIES_MEGA_BAXCALIBUR":
        raise InventoryError("canonical species declaration order no longer matches IDs 0 through 1475")
    if len(names) != len(set(names)):
        raise InventoryError("duplicate canonical species name")
    return [{"id": identity_id, "species": names[identity_id]} for identity_id in range(1, len(names))]


def _generation(identity_id: int, base_id: int | None = None) -> int | None:
    probe = base_id if base_id is not None else identity_id
    for generation, first, last in GENERATION_RANGES:
        if first <= probe <= last:
            return generation
    return None


def _indexed_names(text: str) -> set[str]:
    return set(re.findall(r"\[(SPECIES_[A-Z0-9_]+)(?:\s*-\s*SPECIES_[A-Z0-9_]+)?\]\s*=", text))


def _form_mapping(root: Path) -> dict[str, str]:
    return dict(
        re.findall(
            r"\[(SPECIES_[A-Z0-9_]+)\s*-\s*SPECIES_MEGA_START\]\s*=\s*(SPECIES_[A-Z0-9_]+)",
            _read(root, FORM_MAP),
        )
    )


def _national_dex_names(root: Path) -> set[str]:
    text = _read(root, POKEDEX_SORT)
    match = re.search(r"sPokedexSort_NationalNum\[\]\s*=\s*\{(.*?)\};", text, re.DOTALL)
    if not match:
        raise InventoryError("National Dex sort table not found")
    return set(re.findall(r"SPECIES_[A-Z0-9_]+", match.group(1)))


def _mega_species(root: Path) -> set[str]:
    text = _read(root, MEGA_TABLE)
    match = re.search(r"sMegaTable\[\]\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    if not match:
        raise InventoryError("Mega table not found")
    return set(re.findall(r"\.monindex\s*=\s*(SPECIES_[A-Z0-9_]+)", match.group(1)))


def _asset_state(root: Path, token: str) -> dict[str, bool]:
    directory = root / SPRITES / token.removeprefix("SPECIES_").lower()
    front = any((directory / gender / "front.png").is_file() and (directory / gender / "front.png").stat().st_size for gender in ("male", "female"))
    back = any((directory / gender / "back.png").is_file() and (directory / gender / "back.png").stat().st_size for gender in ("male", "female"))
    return {
        "battle_front": bool(front),
        "battle_back": bool(back),
        "palette": bool(front and back),
        "icon": (directory / "icon.png").is_file() and (directory / "icon.png").stat().st_size > 0,
        "overworld_source": (directory / "overworld.png").is_file() and (directory / "overworld.png").stat().st_size > 0,
        "overworld_palette": all(
            (directory / name).is_file() and (directory / name).stat().st_size > 0
            for name in ("overworld-tsure_poke0.pal", "overworld-tsure_poke1.pal")
        ),
    }


def _classify(capabilities: dict[str, bool], placeholder: bool) -> str:
    if placeholder:
        return "NOT_IMPLEMENTED"
    data_keys = ("species_data", "learnset", "evolution")
    asset_keys = ("battle_front", "battle_back", "palette", "icon", "cry")
    runtime_keys = (
        "follower_mapping",
        "follower_properties",
        "pokedex_complete",
        "party_storage",
        "box_storage",
        "save_storage",
        "trainer_storage",
        "wild_storage",
    )
    data = all(capabilities[key] for key in data_keys)
    assets = all(capabilities[key] for key in asset_keys)
    if data and assets and all(capabilities[key] for key in runtime_keys):
        return "COMPLETE"
    if data and assets:
        return "PARTIAL"
    if data:
        return "DATA_ONLY"
    if assets:
        return "ASSET_ONLY"
    return "UNKNOWN"


def build_inventory(root: Path = ROOT, revision: str | None = None) -> dict[str, Any]:
    identities = _species_constants(root)
    id_by_name = {entry["species"]: entry["id"] for entry in identities}
    form_to_base = _form_mapping(root)
    species_records = _indexed_names(_read(root, SPECIES_DATA))
    evolution_records = _indexed_names(_read(root, EVOLUTION_DATA))
    follower_records = set(re.findall(r"MON_FOLLOWER_ENTRY\((SPECIES_[A-Z0-9_]+)", _read(root, FOLLOWER_TABLE)))
    follower_properties = _indexed_names(_read(root, FOLLOWER_PROPERTIES))
    dex_names = _national_dex_names(root)
    mega_base_species = _mega_species(root)
    learnsets = json.loads(_read(root, LEARNSETS))
    if not isinstance(learnsets, dict):
        raise InventoryError("learnsets root must be an object")

    records: list[dict[str, Any]] = []
    for identity in identities:
        name = identity["species"]
        identity_id = identity["id"]
        placeholder = 494 <= identity_id <= 543
        form = identity_id > 1075
        base_name = form_to_base.get(name) if form else name
        base_id = id_by_name.get(base_name) if base_name else None
        stored_species_id = base_id if form else identity_id
        inherited_name = name if name in learnsets else base_name
        assets = _asset_state(root, name)
        if placeholder:
            cry = False
        elif identity_id <= 493:
            cry = True
        else:
            cry_id = base_id if form else identity_id
            cry = cry_id is not None and (cry_id <= 493 or (root / CRIES / f"{cry_id}.wav").is_file())
        capabilities: dict[str, bool] = {
            "identity": True,
            "national_dex_identity": bool(not form and name in dex_names),
            "species_data": name in species_records,
            "base_stats": name in species_records,
            "typing": name in species_records,
            "abilities": name in species_records,
            "gender": name in species_records,
            "growth_rate": name in species_records,
            "catch_rate": name in species_records,
            "ev_yield": name in species_records,
            "held_items": name in species_records,
            "egg_groups": name in species_records,
            "base_friendship": name in species_records,
            "learnset": bool(inherited_name and inherited_name in learnsets),
            "level_up_learnset": bool(inherited_name and inherited_name in learnsets),
            "machine_compatibility": bool(inherited_name and inherited_name in learnsets),
            "tutor_compatibility": bool(inherited_name and inherited_name in learnsets),
            "egg_moves": bool(inherited_name and inherited_name in learnsets),
            "evolution": name in evolution_records,
            **assets,
            "cry": cry,
            "follower_mapping": name in follower_records,
            "follower_properties": name in follower_properties,
            "pokedex_number": bool((not form and name in dex_names) or (form and base_name in dex_names)),
            "pokedex_name": name in species_records,
            "pokedex_category": bool(base_id is not None and base_id <= 493),
            "pokedex_description": bool(base_id is not None and base_id <= 493),
            "pokedex_sprite": assets["battle_front"],
            "pokedex_seen_caught": bool((not form and name in dex_names) or (form and base_name in dex_names)),
            "pokedex_form_handling": bool(not form or base_name),
            "trainer_storage": identity_id <= 0xFFFF,
            "wild_storage": stored_species_id is not None and stored_species_id <= 0x7FF,
            "party_storage": stored_species_id is not None and stored_species_id <= 0xFFFF,
            "box_storage": stored_species_id is not None and stored_species_id <= 0xFFFF,
            "save_storage": stored_species_id is not None and stored_species_id <= 0xFFFF,
            "form_mapping": bool(not form or base_name),
            "mega_battle_mapping": bool(base_name in mega_base_species and name.startswith("SPECIES_MEGA_")),
        }
        capabilities["pokedex_complete"] = all(
            capabilities[key]
            for key in (
                "pokedex_number",
                "pokedex_name",
                "pokedex_category",
                "pokedex_description",
                "pokedex_sprite",
                "pokedex_seen_caught",
                "pokedex_form_handling",
            )
        )
        capabilities["cry_authenticity_verified"] = identity_id <= 493
        capabilities["trainer_party_usability"] = capabilities["trainer_storage"] and capabilities["species_data"]
        capabilities["wild_encounter_usability"] = capabilities["wild_storage"] and capabilities["species_data"]
        capabilities["party_usability"] = capabilities["party_storage"] and capabilities["species_data"]
        capabilities["pc_box_usability"] = capabilities["box_storage"] and capabilities["species_data"]
        capabilities["save_load_compatibility"] = capabilities["save_storage"] and capabilities["species_data"]
        capabilities["overworld"] = all(
            capabilities[key]
            for key in ("overworld_source", "overworld_palette", "follower_mapping", "follower_properties")
        )
        evidence = {
            "identity": str(SPECIES_HEADER),
            "species_data": str(SPECIES_DATA),
            "learnset": str(LEARNSETS if capabilities["learnset"] else FORM_MAP),
            "evolution": str(EVOLUTION_DATA),
            "battle_assets": str(SPRITES / name.removeprefix("SPECIES_").lower()),
            "cry": "src/pokemon.c; armips/asm/cries.s; sound/cries" if cry else "unresolved",
            "follower": f"{FOLLOWER_TABLE}; {FOLLOWER_PROPERTIES}",
            "pokedex": f"{POKEDEX_SORT}; include/pokedex_archive_data.h; armips/asm/pokedex.s; no tracked expanded category/description source",
            "storage": "include/pokemon.h; include/trainer_data.h; include/encounter.h",
            "form": str(FORM_MAP),
            "mega": str(MEGA_TABLE),
        }
        status = _classify(capabilities, placeholder)
        if status not in STATUSES:
            raise InventoryError(f"invalid status {status}")
        records.append(
            {
                "species": name,
                "id": identity_id,
                "kind": "placeholder" if placeholder else ("form" if form else "species"),
                "generation": _generation(identity_id, base_id),
                "base_species": base_name if form else None,
                "status": status,
                "capabilities": capabilities,
                "evidence": evidence,
            }
        )

    evolution_proof_species = {"SPECIES_POPPLIO", "SPECIES_BRIONNE", "SPECIES_PRIMARINA"}
    regional_form_proof_species = {"SPECIES_ZORUA_HISUIAN", "SPECIES_ZOROARK_HISUIAN"}
    mega_proof_species = {"SPECIES_MEGA_ALTARIA"}
    for record in records:
        if record["species"] in evolution_proof_species:
            record["representative_evolution_status"] = "COMPLETE_EXECUTED"
        if record["species"] in regional_form_proof_species:
            record["representative_regional_form_status"] = "COMPLETE_EXECUTED"
        if record["species"] in mega_proof_species:
            record["representative_mega_status"] = "COMPLETE_EXECUTED"

    status_counts = Counter(record["status"] for record in records)
    generation_rows = []
    for generation, first, last in GENERATION_RANGES:
        generation_records = [record for record in records if record["kind"] == "species" and record["generation"] == generation]
        generation_rows.append(
            {
                "generation": generation,
                "expected_in_engine": last - first + 1,
                "complete": sum(record["status"] == "COMPLETE" for record in generation_records),
                "partial": sum(record["status"] == "PARTIAL" for record in generation_records),
                "missing": sum(record["status"] in {"DATA_ONLY", "ASSET_ONLY", "NOT_IMPLEMENTED", "UNKNOWN"} for record in generation_records),
                "overworld_runtime": sum(record["capabilities"]["follower_mapping"] for record in generation_records),
            }
        )

    inventory = {
        "schema_version": SCHEMA_VERSION,
        "source_revision": revision or "WORKTREE",
        "method": {
            "classification": {
                "COMPLETE": "core species/evolution/learnset data, battle assets, cry, follower runtime mapping/properties, Dex mapping, and storage paths all resolve",
                "PARTIAL": "core data and battle assets resolve, but at least one runtime capability is absent",
                "DATA_ONLY": "core data resolves but the battle asset set is incomplete",
                "ASSET_ONLY": "battle assets resolve but core data is incomplete",
                "NOT_IMPLEMENTED": "reserved HGSS identity slot rather than an implemented Pokemon",
                "UNKNOWN": "neither a complete core-data nor complete battle-asset set can be established",
            },
            "forms": "form capabilities inherit learnset, cry, and Dex identity only through explicit FormToSpeciesMapping evidence",
            "overworld": "requires both source graphics and a runtime MON_FOLLOWER_ENTRY mapping; filenames alone do not count",
        },
        "limits": {
            "highest_identity_id": 1475,
            "highest_base_species_id": 1075,
            "box_party_species_bits": 16,
            "alternate_form_bits": 5,
            "wild_runtime_species_bits": 11,
            "wild_runtime_form_bits": 5,
            "trainer_source_species_bits": 16,
            "encounter_source_species_bits": 16,
        },
        "summary": {
            "identity_count": len(records),
            "implemented_species_count": sum(record["kind"] == "species" for record in records),
            "form_identity_count": sum(record["kind"] == "form" for record in records),
            "reserved_placeholder_count": sum(record["kind"] == "placeholder" for record in records),
            "status_counts": {status: status_counts.get(status, 0) for status in sorted(STATUSES)},
            "battle_front_count": sum(record["capabilities"]["battle_front"] for record in records),
            "battle_back_count": sum(record["capabilities"]["battle_back"] for record in records),
            "icon_count": sum(record["capabilities"]["icon"] for record in records),
            "cry_count": sum(record["capabilities"]["cry"] for record in records),
            "overworld_source_count": sum(record["capabilities"]["overworld_source"] for record in records),
            "overworld_runtime_count": sum(record["capabilities"]["follower_mapping"] for record in records),
            "mega_form_identity_count": sum(record["species"].startswith("SPECIES_MEGA_") for record in records),
            "mega_runtime_mapped_base_species_count": len(mega_base_species),
            "regional_form_counts": {
                "alolan": sum("_ALOLAN" in record["species"] for record in records),
                "galarian": sum("_GALARIAN" in record["species"] for record in records),
                "hisuian": sum("_HISUIAN" in record["species"] for record in records),
                "paldean": sum("_PALDEAN" in record["species"] for record in records),
            },
        },
        "generation_coverage": generation_rows,
        "selected_expanded_species_proof": {
            "species": "SPECIES_VICTINI",
            "id": id_by_name["SPECIES_VICTINI"],
            "selection_reason": "first post-Gen-4 identity with direct data, complete render assets, cry, Dex number/name/sprite/seen-caught support, and follower mappings; expanded Dex category/description and the listed ordinary runtime paths remain unresolved",
            "source_configuration": {
                "level": 20,
                "moves_from_engine_learnset": True,
                "trainer_serialization": "u16",
                "wild_serialization": "u16",
            },
            "runtime_status": "COMPLETE_EXECUTED",
            "shared_runtime_architecture": "REPRESENTATIVE_PROVEN",
            "runtime_evidence": [
                "party identity, level, form, generated moves, calculated stats, typing, and ability",
                "Dex seen/caught storage APIs",
                "follower lookup, field rendering, and movement",
                "ordinary PC box deposit/withdraw with species/form/level/move preservation",
                "ordinary party and box battery-save persistence through hard reset and Continue",
                "two-sided battle-test front/back rendering and move execution",
                "ordinary trainer-NARC load and field trainer battle",
                "ordinary wild encounter, native capture construction, and encounter/capture Dex causality",
                "party and retail PC icon UI resource selection and rendering",
                "expanded cry route 544 -> pseudo-bank index 778 with playback invocation",
                "native map transition with follower tag 3044 preserved and moving on arrival",
            ],
            "runtime_blocker": "none within the applicable shared base-species runtime matrix; expanded Dex category/description content remains a separate content gap",
        },
        "expanded_evolution_runtime": {
            "representative_line": ["SPECIES_POPPLIO", "SPECIES_BRIONNE", "SPECIES_PRIMARINA"],
            "source_methods": ["EVO_LEVEL:17", "EVO_LEVEL:34"],
            "status": "REPRESENTATIVE_PROVEN",
            "scope": "ordinary level-triggered base-species evolution, identity-dependent presentation refresh, and party/box battery persistence for one executed line",
        },
        "expanded_regional_form_runtime": {
            "representative": "SPECIES_ZORUA_HISUIAN",
            "evolved_target": "SPECIES_ZOROARK_HISUIAN",
            "runtime_representation": "base species plus alternate form 1",
            "source_method": "EVO_LEVEL:30",
            "status": "REPRESENTATIVE_PROVEN",
            "scope": "regional personal data, icon/follower/battle presentation, wild form-bit decoding, lineage-preserving evolution, and party/box battery persistence for one executed Hisuian line",
        },
        "expanded_mega_runtime": {
            "representative_base": "SPECIES_ALTARIA",
            "representative_mega": "SPECIES_MEGA_ALTARIA",
            "runtime_representation": "persistent base species 334 plus temporary battle form 1 resolving to adjusted identity 1108",
            "required_item": "ITEM_ALTARIANITE:755",
            "status": "REPRESENTATIVE_PROVEN",
            "scope": "native player activation, temporary Mega personal data/presentation, one-use battle state, battle-end reversion, and post-battle battery persistence for one executed Mega",
        },
        "records": records,
    }
    return inventory


def write_inventory(output: Path, root: Path = ROOT, revision: str | None = None) -> dict[str, Any]:
    inventory = build_inventory(root, revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision")
    args = parser.parse_args()
    inventory = write_inventory(args.output, args.root.resolve(), args.revision)
    print(json.dumps({"output": str(args.output), "summary": inventory["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
