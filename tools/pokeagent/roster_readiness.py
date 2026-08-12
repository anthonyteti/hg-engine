"""Production-readiness analysis for the deterministic HG-Engine roster audit.

The Stage 5A ``status`` field is intentionally historical: it treats every
identity as though it were an ordinary persistent Pokemon.  This module adds
the semantic layer needed for production decisions without rewriting that
evidence.  Temporary battle forms, persistent forms, reserved slots, and the
game's declared roster scope are evaluated against different requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SPECIES_DATA = Path("data/Species.c")
PROJECT_SPEC = Path("01_PROJECT_SPEC.md")
IN_SCOPE_LAST_NATIONAL_DEX = 905

READINESS_STATUSES = {
    "READY",
    "REQUIRED_FUNCTIONAL_GAP",
    "REQUIRED_CONTENT_GAP",
    "AUTHENTICITY_UNVERIFIED",
    "INTENTIONAL_NOT_APPLICABLE",
    "OUT_OF_SCOPE_FOR_GAME",
    "RESERVED_PLACEHOLDER",
    "ARCHITECTURALLY_COVERED_UNEXECUTED",
    "EXTERNAL_CONTENT_BLOCKED",
}

FORM_FAMILIES = {
    "REGIONAL_PERSISTENT",
    "MEGA_TEMPORARY",
    "GIGANTAMAX_OUT_OF_SCOPE",
    "BATTLE_MODE_FORM",
    "COSMETIC_FORM",
    "SIZE_SPECIAL_FORM",
    "TOTEM_OR_LARGE",
    "LORD",
    "ITEM_DRIVE_FORM",
    "WEATHER_OR_STATE_FORM",
    "FILLER_OR_RESERVED",
    "OTHER",
}

FAMILY_REQUIREMENTS = {
    "BASE_SPECIES": {
        "required": ["species_data", "learnset", "evolution", "battle_front", "battle_back", "palette", "icon", "cry", "follower_mapping", "follower_properties", "party_storage", "box_storage", "save_storage", "trainer_storage", "wild_storage", "pokedex_number", "pokedex_name", "pokedex_sprite", "pokedex_seen_caught", "pokedex_category", "pokedex_description"],
        "not_applicable": [],
    },
    "REGIONAL_PERSISTENT": {
        "required": ["species_data", "form_mapping", "battle_front", "battle_back", "palette", "icon", "follower_mapping", "follower_properties", "party_storage", "box_storage", "save_storage"],
        "not_applicable": ["independent_national_dex_identity"],
    },
    "MEGA_TEMPORARY": {
        "required": ["species_data", "form_mapping", "mega_battle_mapping", "battle_front", "battle_back", "palette", "icon", "battle_reversion"],
        "not_applicable": ["ordinary_follower", "persistent_form_storage", "independent_national_dex_identity"],
    },
    "GIGANTAMAX_OUT_OF_SCOPE": {
        "required": [],
        "not_applicable": ["current_game_content", "ordinary_follower", "persistent_form_storage", "independent_national_dex_identity"],
    },
    "FILLER_OR_RESERVED": {
        "required": [],
        "not_applicable": ["gameplay_identity", "battle_runtime", "storage", "dex", "cry", "follower"],
    },
    "OTHER_SPECIAL_FORM": {
        "required": ["species_data", "form_mapping", "battle_front", "battle_back", "palette", "icon"],
        "not_applicable": ["independent_national_dex_identity"],
    },
}


class ReadinessError(ValueError):
    """Raised when production-readiness evidence is inconsistent."""


def _read(root: Path, relative: Path) -> str:
    path = root / relative
    if not path.is_file():
        raise ReadinessError(f"missing readiness evidence: {relative}")
    return path.read_text(encoding="utf-8")


def _decode_c_text(value: str) -> str:
    # Species.c uses a doubled slash because speciesdatagen consumes the text
    # before the normal C compiler.  Accept both forms so this parser remains
    # representation-aware if that generator is simplified later.
    return value.replace(r"\\n", "\n").replace(r"\n", "\n").replace(r'\"', '"').replace(r"\\", "\\")


def species_text_records(root: Path) -> dict[str, dict[str, str]]:
    """Decode the canonical Dex text fields already carried by Species.c."""

    text = _read(root, SPECIES_DATA)
    starts = list(re.finditer(r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{", text, re.MULTILINE))
    records: dict[str, dict[str, str]] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start() : end]
        fields: dict[str, str] = {}
        for key in ("name", "pokedexEntry", "classification"):
            value_match = re.search(rf"\.{key}\s*=\s*\"((?:\\.|[^\"\\])*)\"", block)
            fields[key] = _decode_c_text(value_match.group(1)) if value_match else ""
        records[match.group(1)] = fields
    return records


def validate_dex_content(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate every implemented base-species Dex text record deterministically."""

    text_records = species_text_records(root)
    errors: list[dict[str, Any]] = []
    metrics = {"max_description_characters": 0, "max_description_lines": 0, "max_line_characters": 0, "max_category_characters": 0}
    usable = 0
    for record in records:
        if record["kind"] != "species":
            continue
        fields = text_records.get(record["species"], {})
        description = fields.get("pokedexEntry", "")
        category = fields.get("classification", "")
        lines = description.splitlines() if description else []
        metrics["max_description_characters"] = max(metrics["max_description_characters"], len(description))
        metrics["max_description_lines"] = max(metrics["max_description_lines"], len(lines))
        metrics["max_line_characters"] = max([metrics["max_line_characters"], *map(len, lines)])
        metrics["max_category_characters"] = max(metrics["max_category_characters"], len(category))
        reasons = []
        if not fields:
            reasons.append("MISSING_SPECIES_TEXT_RECORD")
        if not description.strip():
            reasons.append("EMPTY_DESCRIPTION")
        if not category.strip() or category == "????? Pokémon":
            reasons.append("EMPTY_OR_PLACEHOLDER_CATEGORY")
        if "\x00" in description or "\x00" in category:
            reasons.append("UNSUPPORTED_NUL")
        if reasons:
            errors.append({"species": record["species"], "id": record["id"], "reasons": reasons})
        else:
            usable += 1
    return {
        "canonical_source": str(SPECIES_DATA),
        "generator": "tools/source/speciesdatagen/species_data_gen.c",
        "archive_members": {"description": 803, "category_primary": 816, "category_secondary": 823},
        "implemented_base_entries": sum(record["kind"] == "species" for record in records),
        "usable_entries": usable,
        "errors": errors,
        "metrics": metrics,
        "validation": "PASS" if not errors else "FAIL",
    }


def validate_generated_dex_archives(
    root: Path, records: list[dict[str, Any]], rawtext_root: Path | None = None,
) -> dict[str, Any]:
    """Compare speciesdatagen output with canonical Species.c text by identity ID."""

    output_root = rawtext_root or root / "build/rawtext"
    members = {"description": 803, "category_primary": 816, "category_secondary": 823}
    lines: dict[str, list[str]] = {}
    hashes: dict[str, str] = {}
    errors: list[dict[str, Any]] = []
    for role, member in members.items():
        path = output_root / f"{member}.txt"
        if not path.is_file():
            raise ReadinessError(f"missing generated Dex raw text: {path}")
        payload = path.read_bytes()
        hashes[role] = hashlib.sha256(payload).hexdigest()
        lines[role] = payload.decode("utf-8").splitlines()
        if len(lines[role]) != 1476:
            errors.append({"role": role, "reason": "WRONG_IDENTITY_COUNT", "observed": len(lines[role]), "expected": 1476})

    source = species_text_records(root)
    checked = 0
    for record in records:
        if record["kind"] != "species":
            continue
        identity_id = record["id"]
        fields = source[record["species"]]
        expected_description = fields["pokedexEntry"].replace("\n", r"\n")
        expected_category = fields["classification"]
        observed = {
            "description": lines["description"][identity_id] if identity_id < len(lines["description"]) else None,
            "category_primary": lines["category_primary"][identity_id] if identity_id < len(lines["category_primary"]) else None,
            "category_secondary": lines["category_secondary"][identity_id] if identity_id < len(lines["category_secondary"]) else None,
        }
        if observed["description"] != expected_description:
            errors.append({"species": record["species"], "id": identity_id, "reason": "DESCRIPTION_MISMATCH"})
        if observed["category_primary"] != expected_category or observed["category_secondary"] != expected_category:
            errors.append({"species": record["species"], "id": identity_id, "reason": "CATEGORY_MISMATCH"})
        checked += 1
    return {
        "schema_version": 1,
        "rawtext_root": str(output_root.relative_to(root) if output_root.is_relative_to(root) else output_root),
        "identity_rows_per_member": {role: len(value) for role, value in lines.items()},
        "implemented_base_entries_checked": checked,
        "member_sha256": hashes,
        "errors": errors,
        "validation": "PASS" if not errors else "FAIL",
    }


def form_family(species: str) -> str:
    if "_FILLER_" in species:
        return "FILLER_OR_RESERVED"
    if species.startswith("SPECIES_GIGANTAMAX_"):
        return "GIGANTAMAX_OUT_OF_SCOPE"
    if species.startswith("SPECIES_MEGA_"):
        return "MEGA_TEMPORARY"
    if any(marker in species for marker in ("_ALOLAN", "_GALARIAN", "_HISUIAN", "_PALDEAN")) and "_LARGE" not in species:
        return "REGIONAL_PERSISTENT"
    if any(marker in species for marker in ("_TOTEM", "_LARGE")):
        return "TOTEM_OR_LARGE"
    if species.endswith(("_LORD", "_LADY")):
        return "LORD"
    if any(marker in species for marker in ("_DRIVE", "_PLATE", "_MEMORY")):
        return "ITEM_DRIVE_FORM"
    if any(marker in species for marker in ("_SUNNY", "_RAINY", "_SNOWY", "_SANDY", "_FROST", "_HEAT", "_WASH", "_FAN", "_MOW")):
        return "WEATHER_OR_STATE_FORM"
    if any(marker in species for marker in ("_SMALL", "_LARGE", "_SUPER", "_FAMILY_OF_THREE")):
        return "SIZE_SPECIAL_FORM"
    if any(marker in species for marker in ("_CAP", "_COSPLAY", "_FANCY", "_POKE_BALL", "_FLOWER", "_TRIM", "_SWEET", "_CREAM", "_FEMALE")):
        return "COSMETIC_FORM"
    if any(marker in species for marker in ("_ATTACK", "_DEFENSE", "_SPEED", "_SKY", "_ORIGIN", "_THERIAN", "_BLACK", "_WHITE", "_BLADE", "_SCHOOL", "_BUSTED", "_CROWNED", "_ETERNAMAX", "_HERO", "_UNBOUND", "_ASH", "_COMPLETE", "_ZEN", "_POWER_CONSTRUCT")):
        return "BATTLE_MODE_FORM"
    return "OTHER"


def _required_missing(capabilities: dict[str, bool], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not capabilities.get(name, False)]


def _cry_classification(record: dict[str, Any]) -> str:
    if record["kind"] == "placeholder":
        return "NOT_APPLICABLE"
    if record["kind"] == "form":
        return "NOT_APPLICABLE_INHERITS_BASE_ROUTE"
    if not record["capabilities"]["cry"]:
        return "MISSING"
    if record["id"] <= 493:
        return "AUTHENTIC_PROVENANCE_VERIFIED"
    return "ROUTED_SOURCE_PRESENT_UNVERIFIED"


def classify_record(record: dict[str, Any], dex_fields: dict[str, str]) -> dict[str, Any]:
    """Classify one historical audit record under production semantics."""

    species = record["species"]
    caps = record["capabilities"]
    family = "RESERVED_PLACEHOLDER" if record["kind"] == "placeholder" else ("BASE_SPECIES" if record["kind"] == "species" else form_family(species))
    base_id = record["id"] if record["kind"] == "species" else record.get("base_species_id")
    if base_id is None and record["kind"] == "form":
        # roster_inventory annotates this before calling the classifier.
        base_id = 0
    dex_ready = bool(dex_fields.get("pokedexEntry", "").strip() and dex_fields.get("classification", "").strip() not in {"", "????? Pokémon"})
    cry = _cry_classification(record)
    required: list[str] = []
    optional: list[str] = []
    not_applicable: list[str] = []
    evidence: list[str] = []

    if record["kind"] == "placeholder":
        scope = "RESERVED_PLACEHOLDER"
        readiness = "RESERVED_PLACEHOLDER"
        not_applicable = ["gameplay_data", "battle_assets", "storage", "dex", "cry", "follower"]
        evidence.append("HGSS_RESERVED_IDENTITY_WINDOW_494_543")
    elif record["kind"] == "species":
        scope = "IN_SCOPE" if record["national_dex_number"] <= IN_SCOPE_LAST_NATIONAL_DEX else "OUT_OF_SCOPE_FOR_GAME"
        required = _required_missing(
            caps,
            (
                "species_data", "learnset", "evolution", "battle_front", "battle_back", "palette", "icon",
                "cry", "follower_mapping", "follower_properties", "party_usability", "pc_box_usability",
                "save_load_compatibility", "trainer_party_usability", "wild_encounter_usability",
                "pokedex_number", "pokedex_name", "pokedex_sprite", "pokedex_seen_caught",
            ),
        )
        if not dex_ready:
            required.append("expanded_dex_content")
        optional = [] if cry == "AUTHENTIC_PROVENANCE_VERIFIED" else ["cry_authenticity_provenance"]
        evidence.extend(("STAGE_5B_SHARED_BASE_RUNTIME_PROVEN", "SPECIES_C_DEX_TEXT_PIPELINE"))
        if scope == "OUT_OF_SCOPE_FOR_GAME":
            readiness = "OUT_OF_SCOPE_FOR_GAME"
        elif required:
            readiness = "REQUIRED_FUNCTIONAL_GAP" if any(item != "expanded_dex_content" for item in required) else "REQUIRED_CONTENT_GAP"
        else:
            readiness = "READY"
    else:
        base_national_dex = record.get("base_national_dex_number")
        scope = "IN_SCOPE" if base_national_dex is not None and base_national_dex <= IN_SCOPE_LAST_NATIONAL_DEX else "OUT_OF_SCOPE_FOR_GAME"
        if family == "FILLER_OR_RESERVED":
            scope = "RESERVED_PLACEHOLDER"
            readiness = "RESERVED_PLACEHOLDER"
            not_applicable = ["gameplay_identity", "battle_runtime", "storage", "dex", "cry", "follower"]
        elif family == "GIGANTAMAX_OUT_OF_SCOPE":
            scope = "OUT_OF_SCOPE_FOR_GAME"
            readiness = "OUT_OF_SCOPE_FOR_GAME"
            not_applicable = ["dynamax_runtime", "ordinary_follower", "persistent_dex_identity"]
        elif record["id"] >= 1428:
            # These are the later Legends: Z-A Mega identity block.  The
            # project content boundary is through Legends: Arceus (#905), and
            # no design decision opts these newer forms into production even
            # when their base species is older.
            scope = "OUT_OF_SCOPE_FOR_GAME"
            readiness = "OUT_OF_SCOPE_FOR_GAME"
            not_applicable = ["current_game_content_selection"]
        elif scope == "OUT_OF_SCOPE_FOR_GAME":
            readiness = "OUT_OF_SCOPE_FOR_GAME"
        elif family == "MEGA_TEMPORARY":
            required = _required_missing(caps, ("species_data", "battle_front", "battle_back", "palette", "icon", "form_mapping"))
            if not caps.get("mega_battle_mapping", False) and species != "SPECIES_MEGA_RAYQUAZA":
                required.append("mega_battle_mapping")
            not_applicable = ["ordinary_follower", "persistent_form_storage", "independent_national_dex_identity"]
            evidence.append("STAGE_5E_REPRESENTATIVE_MEGA_ARCHITECTURE_PROVEN")
            if species == "SPECIES_MEGA_RAYQUAZA":
                evidence.append("MEGA_MOVE_TRIGGER_MAPPING_DRAGON_ASCENT")
            readiness = "REQUIRED_FUNCTIONAL_GAP" if required else "READY"
        elif family == "REGIONAL_PERSISTENT":
            required = _required_missing(caps, ("species_data", "battle_front", "battle_back", "palette", "icon", "form_mapping", "follower_mapping", "follower_properties", "party_usability", "pc_box_usability", "save_load_compatibility"))
            not_applicable = ["independent_national_dex_identity"]
            evidence.append("STAGE_5D_REPRESENTATIVE_REGIONAL_ARCHITECTURE_PROVEN")
            readiness = "REQUIRED_FUNCTIONAL_GAP" if required else "READY"
        else:
            required = _required_missing(caps, ("species_data", "battle_front", "battle_back", "palette", "icon", "form_mapping"))
            not_applicable = ["independent_national_dex_identity"]
            if not caps.get("follower_mapping", False):
                not_applicable.append("ordinary_follower_unless_exposed_by_game_content")
            evidence.append("FORM_FAMILY_STATIC_CONTRACT")
            readiness = "REQUIRED_FUNCTIONAL_GAP" if required else "ARCHITECTURALLY_COVERED_UNEXECUTED"

    if readiness not in READINESS_STATUSES:
        raise ReadinessError(f"invalid readiness {readiness}: {species}")
    return {
        "scope": scope,
        "family": family,
        "readiness": readiness,
        "required_gaps": sorted(required),
        "optional_gaps": sorted(optional),
        "not_applicable": sorted(not_applicable),
        "reason_codes": sorted(set(evidence)),
        "content": {
            "dex": "NOT_APPLICABLE" if record["kind"] != "species" else ("READY" if dex_ready else "MISSING"),
            "cry_runtime": "READY" if caps.get("cry", False) else ("NOT_APPLICABLE" if record["kind"] != "species" else "MISSING"),
            "cry_authenticity": cry,
        },
    }


def apply_production_readiness(root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    """Annotate inventory records and return a deterministic summary."""

    spec = _read(root, PROJECT_SPEC)
    if "National Dex #905" not in spec or "Dynamax or Gigantamax" not in spec:
        raise ReadinessError("project roster/gimmick scope markers changed")
    records = inventory["records"]
    id_by_name = {record["species"]: record["id"] for record in records}
    dex_by_name = {
        record["species"]: record["national_dex_number"]
        for record in records
        if record["kind"] == "species"
    }
    dex_records = species_text_records(root)
    for record in records:
        if record["kind"] == "form":
            record["base_species_id"] = id_by_name.get(record["base_species"])
            record["base_national_dex_number"] = dex_by_name.get(record["base_species"])
        record["production"] = classify_record(record, dex_records.get(record["species"], {}))

    readiness_counts = Counter(record["production"]["readiness"] for record in records)
    scope_counts = Counter(record["production"]["scope"] for record in records)
    family_counts = Counter(record["production"]["family"] for record in records)
    cry_counts = Counter(record["production"]["content"]["cry_authenticity"] for record in records)
    generation_rows = []
    for generation in range(1, 10):
        generation_records = [record for record in records if record["kind"] == "species" and record["generation"] == generation]
        generation_rows.append(
            {
                "generation": generation,
                "base_species_count": len(generation_records),
                "in_scope_count": sum(record["production"]["scope"] == "IN_SCOPE" for record in generation_records),
                "functional_gap_count": sum(record["production"]["readiness"] == "REQUIRED_FUNCTIONAL_GAP" for record in generation_records),
                "dex_content_gap_count": sum("expanded_dex_content" in record["production"]["required_gaps"] for record in generation_records),
                "cry_runtime_gap_count": sum(record["production"]["content"]["cry_runtime"] == "MISSING" for record in generation_records),
                "cry_authenticity_unverified_count": sum(record["production"]["content"]["cry_authenticity"] == "ROUTED_SOURCE_PRESENT_UNVERIFIED" for record in generation_records),
                "other_gap_count": sum(bool(set(record["production"]["required_gaps"]) - {"expanded_dex_content", "cry"}) for record in generation_records),
            }
        )

    exceptional_names = {
        "SPECIES_GIGANTAMAX_TOXTRICITY_LOW_KEY",
        "SPECIES_GIGANTAMAX_URSHIFU_RAPID_STRIKE",
        "SPECIES_MEGA_TATSUGIRI_STRETCHY",
        "SPECIES_MEGA_BAXCALIBUR",
        "SPECIES_ALCREMIE_FILLER_1",
        "SPECIES_ALCREMIE_FILLER_2",
    }
    exceptions = [
        {
            "species": record["species"],
            "audit_status": record["status"],
            "family": record["production"]["family"],
            "scope": record["production"]["scope"],
            "readiness": record["production"]["readiness"],
            "action": (
                "preserve engine record; Gigantamax is outside project scope"
                if record["production"]["family"] == "GIGANTAMAX_OUT_OF_SCOPE"
                else "preserve structural filler; do not invent gameplay content"
                if record["production"]["family"] == "FILLER_OR_RESERVED"
                else "preserve source-backed future Mega data; base species is outside the #905 production scope"
            ),
        }
        for record in records
        if record["species"] in exceptional_names
    ]
    dex_validation = validate_dex_content(root, records)
    in_scope_bases = [record for record in records if record["kind"] == "species" and record["production"]["scope"] == "IN_SCOPE"]
    regional = [record for record in records if record["production"]["family"] == "REGIONAL_PERSISTENT" and record["production"]["scope"] == "IN_SCOPE"]
    megas = [record for record in records if record["production"]["family"] == "MEGA_TEMPORARY" and record["production"]["scope"] == "IN_SCOPE"]
    return {
        "schema_version": 1,
        "game_scope": {
            "base_species": "National Dex identities through 905",
            "regional_forms": "persistent relevant forms through the scoped base roster",
            "mega_forms": "temporary battle identities for scoped base species",
            "gigantamax": "OUT_OF_SCOPE_FOR_GAME",
        },
        "readiness_counts": {status: readiness_counts.get(status, 0) for status in sorted(READINESS_STATUSES)},
        "scope_counts": dict(sorted(scope_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "family_requirements": FAMILY_REQUIREMENTS,
        "cry_classification_counts": dict(sorted(cry_counts.items())),
        "generation_base_status": generation_rows,
        "dex_content": dex_validation,
        "required_base_species": {
            "count": len(in_scope_bases),
            "ready_count": sum(record["production"]["readiness"] == "READY" for record in in_scope_bases),
            "functional_gap_count": sum(record["production"]["readiness"] == "REQUIRED_FUNCTIONAL_GAP" for record in in_scope_bases),
            "content_gap_count": sum(record["production"]["readiness"] == "REQUIRED_CONTENT_GAP" for record in in_scope_bases),
            "cry_runtime_ready_count": sum(record["production"]["content"]["cry_runtime"] == "READY" for record in in_scope_bases),
        },
        "regional_static_audit": {
            "in_scope_count": len(regional),
            "ready_count": sum(record["production"]["readiness"] == "READY" for record in regional),
            "required_gap_count": sum(bool(record["production"]["required_gaps"]) for record in regional),
        },
        "mega_static_audit": {
            "in_scope_count": len(megas),
            "ready_count": sum(record["production"]["readiness"] == "READY" for record in megas),
            "required_gap_count": sum(bool(record["production"]["required_gaps"]) for record in megas),
        },
        "exceptional_identities": exceptions,
        "trainer_form_serialization": {
            "classification": "ARCHITECTURALLY_COVERED_UNEXECUTED",
            "evidence": "src/field/enemy_party.c decodes form bits from the trainer u16 species field, calls CreateMon, writes MON_DATA_FORM, and resolves PokeOtherFormMonsNoGet; Stage 5D executed the analogous wild form-bit result",
        },
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated Stage 5F Dex text archives")
    parser.add_argument("--inventory", type=Path, default=Path("docs/data/hgengine_roster_inventory.json"))
    parser.add_argument("--rawtext-root", type=Path, default=Path("build/rawtext"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = validate_generated_dex_archives(Path.cwd(), inventory["records"], args.rawtext_root)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["validation"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
