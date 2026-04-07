"""
military.py — Extract military forces and extended war data from an EU5Save.

Covers:
  - Unit type catalog (loaded once from game config files)
  - Country military snapshots (regiment counts + strengths per country)
  - War participant snapshots (scores + cumulative losses per participant)
  - Battle detection (diff-based; returns only newly-seen battles)
  - Siege state extraction (full current state for upsert)

Slot order for 8-element battle force arrays:
  [infantry, cavalry, artillery, auxiliary, galley, light_ship, transport, heavy_ship]
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.parser.save_loader import EU5Save

logger = logging.getLogger(__name__)

# ── Unit category → slot index ────────────────────────────────────────────────

CATEGORY_SLOT = {
    "army_infantry":   0,
    "army_cavalry":    1,
    "army_artillery":  2,
    "army_auxiliary":  3,
    "navy_galley":     4,
    "navy_light_ship": 5,
    "navy_transport":  6,
    "navy_heavy_ship": 7,
}

SLOT_NAMES = [
    "infantry", "cavalry", "artillery", "auxiliary",
    "galley", "light_ship", "transport", "heavy_ship",
]

# category → (count_col, strength_col) for country_military_snapshots
CATEGORY_COLS = {
    "army_infantry":   ("infantry_count",   "infantry_strength"),
    "army_cavalry":    ("cavalry_count",    "cavalry_strength"),
    "army_artillery":  ("artillery_count",  "artillery_strength"),
    "army_auxiliary":  ("auxiliary_count",  "auxiliary_strength"),
    "navy_galley":     ("galley_count",     "galley_strength"),
    "navy_light_ship": ("light_ship_count", "light_ship_strength"),
    "navy_transport":  ("transport_count",  "transport_strength"),
    "navy_heavy_ship": ("heavy_ship_count", "heavy_ship_strength"),
}

# ── Unit type catalog ─────────────────────────────────────────────────────────

def load_unit_type_catalog(game_install_path: str | Path) -> dict[str, dict]:
    """
    Parse unit type definitions from the game install and return a mapping:
        { type_key: { "category": str, "max_strength": float } }

    Tries several candidate subdirectories under game_install_path since the
    exact layout varies between EU5 versions/builds.  Returns an empty dict
    (not an error) when no directory is found — callers decide whether to
    treat that as fatal.
    """
    base = Path(game_install_path)
    # Candidate paths, most-likely first
    candidates = [
        base / "game" / "in_game" / "common" / "unit_types",   # EU5 confirmed
        base / "game" / "common" / "unit_types",
        base / "common" / "unit_types",
        base / "game" / "common" / "units",
        base / "common" / "units",
    ]

    unit_types_dir: Path | None = None
    for c in candidates:
        if c.exists():
            unit_types_dir = c
            break

    if unit_types_dir is None:
        tried = ", ".join(str(c) for c in candidates)
        logger.warning("unit_types dir not found (tried: %s)", tried)
        return {}

    catalog: dict[str, dict] = {}

    # Simple regex parser — we don't need a full PDX script parser here.
    # Each unit type block looks like:
    #   type_key = {
    #       category = army_infantry
    #       max_strength = 1.0
    #       ...
    #   }
    block_re    = re.compile(r'^(\w+)\s*=\s*\{([^}]*)\}', re.MULTILINE | re.DOTALL)
    category_re = re.compile(r'\bcategory\s*=\s*(\w+)')
    max_str_re  = re.compile(r'\bmax_strength\s*=\s*([0-9.]+)')

    for txt_file in sorted(unit_types_dir.glob("*.txt")):
        try:
            text = txt_file.read_text(encoding="utf-8-sig", errors="replace")
            for m in block_re.finditer(text):
                type_key = m.group(1)
                body     = m.group(2)
                cat_m    = category_re.search(body)
                ms_m     = max_str_re.search(body)
                if cat_m:
                    catalog[type_key] = {
                        "category":     cat_m.group(1),
                        "max_strength": float(ms_m.group(1)) if ms_m else 1.0,
                    }
        except Exception:
            logger.warning("Failed to parse unit types from %s", txt_file, exc_info=True)

    logger.info("Loaded unit type catalog: %d types from %s", len(catalog), unit_types_dir)
    return catalog


# ── Country military snapshots ────────────────────────────────────────────────

def extract_country_military(
    save: EU5Save,
    unit_type_catalog: dict[str, dict],
    active_war_country_ids: set[int],
    rank_threshold: int = 200,
) -> list[dict[str, Any]]:
    """
    Return one dict per country to write into country_military_snapshots.

    Filter: always include active_war_country_ids; for peaceful countries,
    only include those whose score_place is known AND exceeds rank_threshold.
    Countries with no score_place field are included by default (conservative).

    strength values are the raw game values from subunit.strength
    (absent field = max_strength from catalog; if type unknown, defaults to 1.0).
    """
    countries_db  = save.raw.get("countries", {}).get("database", {})
    subunits_db   = save.raw.get("subunit_manager", {}).get("database", {})
    tags_map      = save.raw.get("countries", {}).get("tags", {})

    n_real = 0
    n_passed_rank = 0
    n_with_subunits = 0
    n_nonzero = 0

    results: list[dict[str, Any]] = []

    for cid_str, cdata in countries_db.items():
        if not isinstance(cdata, dict):
            continue
        if cdata.get("country_type") != "Real":
            continue

        n_real += 1

        try:
            cid = int(cid_str)
        except ValueError:
            continue

        # Apply rank filter for peaceful countries.
        # Only skip when score_place is explicitly known to be bad.
        # If score_place is None (field absent in EU5), include the country.
        if cid not in active_war_country_ids:
            score_obj = cdata.get("score")
            score_place = (
                score_obj.get("score_place")
                if isinstance(score_obj, dict)
                else None
            )
            if score_place is not None and score_place > rank_threshold:
                continue

        n_passed_rank += 1

        # Count subunits by category
        owned_subunit_ids = cdata.get("owned_subunits", [])
        if not isinstance(owned_subunit_ids, list):
            owned_subunit_ids = []

        if owned_subunit_ids:
            n_with_subunits += 1

        # Accumulate per-category: count and total strength
        counts: dict[str, int]   = {c: 0 for c in CATEGORY_COLS}
        strengths: dict[str, float] = {c: 0.0 for c in CATEGORY_COLS}

        for sid in owned_subunit_ids:
            sdata = subunits_db.get(str(sid))
            if not isinstance(sdata, dict):
                continue
            utype = sdata.get("type", "")
            type_info = unit_type_catalog.get(utype)
            if type_info is None:
                continue
            category = type_info.get("category")
            if category not in CATEGORY_COLS:
                continue
            max_str = type_info.get("max_strength", 1.0)
            current_str = sdata.get("strength", max_str)  # absent = full strength
            counts[category]    += 1
            strengths[category] += current_str

        army_count  = sum(counts[c]     for c in ("army_infantry", "army_cavalry", "army_artillery", "army_auxiliary"))
        army_str    = sum(strengths[c]  for c in ("army_infantry", "army_cavalry", "army_artillery", "army_auxiliary"))
        navy_count  = sum(counts[c]     for c in ("navy_galley", "navy_light_ship", "navy_transport", "navy_heavy_ship"))
        navy_str    = sum(strengths[c]  for c in ("navy_galley", "navy_light_ship", "navy_transport", "navy_heavy_ship"))

        if army_count > 0 or navy_count > 0:
            n_nonzero += 1

        # Skip countries with zero forces (nothing to record)
        if army_count == 0 and navy_count == 0:
            continue

        row: dict[str, Any] = {
            "country_id":  cid,
            "country_tag": tags_map.get(cid_str, ""),
            "army_count":  army_count,
            "army_strength": army_str,
            "navy_count":  navy_count,
            "navy_strength": navy_str,
        }
        for cat, (cnt_col, str_col) in CATEGORY_COLS.items():
            row[cnt_col] = counts[cat]
            row[str_col] = round(strengths[cat], 5)

        results.append(row)

    logger.info(
        "extract_country_military: real=%d, passed_rank=%d, with_subunits=%d, "
        "nonzero_forces=%d, subunit_db_size=%d, result_rows=%d",
        n_real, n_passed_rank, n_with_subunits, n_nonzero, len(subunits_db), len(results),
    )
    if n_passed_rank > 0 and n_with_subunits == 0:
        logger.warning(
            "No countries had owned_subunits — 'owned_subunits' field may be "
            "absent or named differently in this EU5 save version."
        )
    if n_passed_rank > 0 and len(subunits_db) == 0:
        logger.warning(
            "subunit_manager.database is empty — the unit data path may be wrong. "
            "Check if EU5 stores units elsewhere (e.g. unit_manager.database)."
        )

    return results


# ── War participant snapshots ─────────────────────────────────────────────────

def extract_war_participant_snapshots(save: EU5Save) -> dict[str, list[dict[str, Any]]]:
    """
    For every active war (no end_date), return per-participant snapshot data.

    Returns { war_id: [ participant_snapshot_dict, ... ] }

    Each dict contains: country_id, country_tag, side,
    score_combat, score_siege, score_joining, losses_json.
    """
    wm      = save.raw.get("war_manager", {}).get("database", {})
    tags    = save.raw.get("countries", {}).get("tags", {})
    result: dict[str, list[dict]] = {}

    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue
        if wdata.get("end_date"):
            continue  # only active wars

        participants_raw = wdata.get("all", [])
        if not isinstance(participants_raw, list):
            continue

        rows = []
        for p in participants_raw:
            if not isinstance(p, dict):
                continue
            country_id = p.get("country")
            if country_id is None:
                continue

            history = p.get("history", {})
            request = history.get("request", {}) if isinstance(history, dict) else {}
            joined  = history.get("joined",  {}) if isinstance(history, dict) else {}

            side   = request.get("side", "Unknown")
            scores = joined.get("score", {}) if isinstance(joined, dict) else {}
            losses_block = joined.get("losses", {}) if isinstance(joined, dict) else {}
            losses_data  = losses_block.get("losses") if isinstance(losses_block, dict) else None

            rows.append({
                "country_id":    country_id,
                "country_tag":   tags.get(str(country_id), ""),
                "side":          side,
                "score_combat":  scores.get("Combat",     0) if isinstance(scores, dict) else 0,
                "score_siege":   scores.get("Siege",      0) if isinstance(scores, dict) else 0,
                "score_joining": scores.get("JoiningWar", 0) if isinstance(scores, dict) else 0,
                "losses_json":   json.dumps(losses_data) if losses_data else None,
            })

        if rows:
            result[wid] = rows

    return result


# ── Battle detection ──────────────────────────────────────────────────────────

def extract_new_battles(
    save: EU5Save,
    prev_battle_states: dict[str, dict],
) -> tuple[list[dict[str, Any]], dict[str, dict]]:
    """
    Detect battles that are new since the previous snapshot.

    A battle is "new" when war_manager.database[wid].battle.date differs
    from prev_battle_states[wid]["date"], OR the war has no prior state.

    Returns:
        (new_battle_dicts, updated_states)
        new_battle_dicts: list of dicts ready for db.upsert_battle()
        updated_states:   pass back in as prev_battle_states next call
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    updated_states: dict[str, dict] = {}
    new_battles: list[dict[str, Any]] = []

    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue

        battle = wdata.get("battle")
        if not isinstance(battle, dict):
            continue

        b_date     = battle.get("date")
        b_location = battle.get("location")
        if b_date is None:
            continue

        updated_states[wid] = {"date": b_date, "location": b_location}

        prev = prev_battle_states.get(wid, {})
        if prev.get("date") == b_date and prev.get("location") == b_location:
            continue  # same battle as last snapshot — already recorded

        # New battle — extract full detail
        att  = battle.get("attacker", {})
        defn = battle.get("defender", {})

        def _who(side_dict: dict) -> dict:
            return side_dict.get("who", {}) if isinstance(side_dict, dict) else {}

        att_who  = _who(att)
        def_who  = _who(defn)

        # Determine is_land from whether any non-zero value appears in slots 4-7
        forces_att = att.get("total", [0] * 8)
        forces_def = defn.get("total", [0] * 8)
        naval_slots = [4, 5, 6, 7]
        is_land = not any(
            (forces_att[i] if i < len(forces_att) else 0) != 0 or
            (forces_def[i] if i < len(forces_def) else 0) != 0
            for i in naval_slots
        )

        new_battles.append({
            "war_id":               wid,
            "game_date":            str(b_date),
            "location_id":          b_location,
            "is_land":              is_land,
            "war_attacker_win":     battle.get("war_attacker_win"),
            "war_score_delta":      battle.get("war_score"),
            "attacker_country_id":  att_who.get("country"),
            "attacker_character_id": att.get("character"),
            "attacker_forces":      json.dumps(_pad8(forces_att)),
            "attacker_losses":      json.dumps(_pad8(att.get("losses", []))),
            "attacker_imprisoned":  json.dumps(_pad8(att.get("imprisoned", []))),
            "attacker_tradition":   att_who.get("tradition"),
            "attacker_experience":  att_who.get("experience"),
            "defender_country_id":  def_who.get("country"),
            "defender_character_id": defn.get("character"),
            "defender_forces":      json.dumps(_pad8(forces_def)),
            "defender_losses":      json.dumps(_pad8(defn.get("losses", []))),
            "defender_imprisoned":  json.dumps(_pad8(defn.get("imprisoned", []))),
            "defender_tradition":   def_who.get("tradition"),
            "defender_experience":  def_who.get("experience"),
        })

    return new_battles, updated_states


def _pad8(arr: list) -> list:
    """Ensure the list is exactly 8 elements (pad with 0 or truncate)."""
    arr = list(arr) if arr else []
    return (arr + [0] * 8)[:8]


# ── Siege extraction ──────────────────────────────────────────────────────────

def extract_sieges(
    save: EU5Save,
    war_participant_index: dict[int, list[str]],
) -> list[dict[str, Any]]:
    """
    Return current siege state for each active siege in siege_manager.database.

    war_participant_index: { country_id: [war_id, ...] } mapping attackers
    to their active wars — used to infer war_id for each siege.

    Each returned dict is suitable for db.upsert_siege().
    """
    sm    = save.raw.get("siege_manager", {}).get("database", {})
    results: list[dict[str, Any]] = []

    for sid_str, sdata in sm.items():
        if not isinstance(sdata, dict):
            continue

        attacker_ids: list[int] = sdata.get("countries", [])
        if not isinstance(attacker_ids, list):
            attacker_ids = []

        # Infer war_id: find a war where any attacker country is a participant
        war_id: str | None = None
        for ac in attacker_ids:
            wars_for_country = war_participant_index.get(ac, [])
            if wars_for_country:
                war_id = wars_for_country[0]  # take first match
                break

        results.append({
            "siege_game_id":         str(sid_str),
            "location_id":           sdata.get("location"),
            "war_id":                war_id,
            "attacker_country_ids":  json.dumps(attacker_ids),
            "defender_country_id":   sdata.get("defender"),
            "besieging_total":       sdata.get("total", 0),
            "siege_day":             sdata.get("day"),
            "duration":              sdata.get("duration"),
            "morale":                sdata.get("morale"),
            "siege_dice":            sdata.get("siege_dice"),
            "siege_status":          sdata.get("siege_status"),
        })

    return results


def build_war_participant_index(save: EU5Save) -> dict[int, list[str]]:
    """
    Build { country_id: [war_id, ...] } for all active-war attacker-side participants.
    Used to link sieges to wars.
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    index: dict[int, list[str]] = {}
    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue
        if wdata.get("end_date"):
            continue
        for p in wdata.get("all", []):
            if not isinstance(p, dict):
                continue
            cid  = p.get("country")
            side = p.get("history", {}).get("request", {}).get("side", "")
            if cid is not None and side == "Attacker":
                index.setdefault(cid, []).append(wid)
    return index


def build_active_war_country_ids(save: EU5Save) -> set[int]:
    """Return set of all country IDs (any side) in active wars."""
    wm = save.raw.get("war_manager", {}).get("database", {})
    ids: set[int] = set()
    for wdata in wm.values():
        if not isinstance(wdata, dict):
            continue
        if wdata.get("end_date"):
            continue
        for p in wdata.get("all", []):
            if isinstance(p, dict) and p.get("country") is not None:
                ids.add(p["country"])
    return ids
