"""
geography.py — Extract location + province data from an EU5 save

Functions:
    extract_location_statics(save)       → list[dict]  (written once per location)
    extract_location_snapshot_rows(save)  → list[dict]  (per owned location per snapshot)
    extract_province_statics(save)        → list[dict]  (written once per province)
    extract_province_snapshot_rows(save)   → list[dict]  (per owned province per snapshot)
    detect_location_events(save, prev_state) → (events, new_state)
"""

from __future__ import annotations

import logging
from typing import Any

from backend.parser.save_loader import EU5Save
from backend.parser.eu5.geography_index import GeographyIndex

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────

def _build_location_slug_index(save: EU5Save) -> dict[int, str]:
    """Return ``{location_id: slug}`` from ``metadata.compatibility.locations``.

    The save stores all known location slugs as a flat array; the
    location_id (1-based, matching ``locations.locations`` keys) is
    ``index + 1``.  Verified against autosave.eu5 on 2026-04-07: 28 573
    slugs, id 1 → 'stockholm', id 2 → 'norrtalje'.
    """
    slugs = (
        save.raw.get("metadata", {})
        .get("compatibility", {})
        .get("locations", [])
    )
    if not isinstance(slugs, list):
        return {}
    return {i + 1: s for i, s in enumerate(slugs) if isinstance(s, str)}


def _build_province_def_index(save: EU5Save) -> dict[int, str]:
    """Return ``{province_id: province_definition_slug}``."""
    db = save.raw.get("provinces", {}).get("database", {})
    out: dict[int, str] = {}
    for pid_str, pdata in db.items():
        if not isinstance(pdata, dict):
            continue
        pdef = pdata.get("province_definition")
        if isinstance(pdef, str):
            try:
                out[int(pid_str)] = pdef
            except (TypeError, ValueError):
                continue
    return out


# ── Owner Map ────────────────────────────────────────────────────────────

def _build_owner_map(save: EU5Save) -> dict[int, dict]:
    """Build {location_id: {"owner_id": int, "owner_tag": str}} from countries.

    In EU5, ownership is declared on the country side:
        countries.database.{country_id}.owned_locations = [loc_id, ...]
    rather than on the location side, so we invert the relationship here.
    """
    owner_map: dict[int, dict] = {}
    countries_db = save.raw.get("countries", {}).get("database", {})
    for country_id_str, country_data in countries_db.items():
        if not isinstance(country_data, dict):
            continue
        tag = save.tag_index.get(country_id_str)
        if not tag:
            continue
        owned_locs = country_data.get("owned_locations", [])
        if not isinstance(owned_locs, list):
            continue
        try:
            country_id = int(country_id_str)
        except (TypeError, ValueError):
            continue
        for loc_id in owned_locs:
            try:
                owner_map[int(loc_id)] = {"owner_id": country_id, "owner_tag": tag}
            except (TypeError, ValueError):
                continue
    return owner_map


# ── Location Statics ─────────────────────────────────────────────────────

def extract_location_statics(
    save: EU5Save,
    geo_index: GeographyIndex | None = None,
) -> list[dict]:
    """Extract static metadata for all owned locations.

    Returns one dict per owned location with fields matching the `locations`
    table schema.  Only locations present in the owner map are included.

    When ``geo_index`` is provided, each row is enriched with the
    canonical slug (resolved from the save's
    ``metadata.compatibility.locations`` array) and the full geographic
    chain (province_def → area → region → sub_continent → continent),
    looked up via the location's ``province`` int → province_definition.
    """
    locs_db = save.raw.get("locations", {}).get("locations", {})
    owner_map = _build_owner_map(save)
    slug_index = _build_location_slug_index(save)
    prov_def_index = _build_province_def_index(save)
    results: list[dict] = []

    for loc_id_str, loc in locs_db.items():
        if not isinstance(loc, dict):
            continue
        loc_id = int(loc_id_str)
        if loc_id not in owner_map:
            continue

        province_id = loc.get("province")
        province_def = prov_def_index.get(province_id) if province_id is not None else None
        chain: dict[str, str | None] = {
            "area": None, "region": None, "sub_continent": None, "continent": None,
        }
        if geo_index is not None and province_def:
            ch = geo_index.chain_for_province(province_def)
            chain["area"]          = ch["area"]
            chain["region"]        = ch["region"]
            chain["sub_continent"] = ch["sub_continent"]
            chain["continent"]     = ch["continent"]

        results.append({
            "id": loc_id,
            "slug": slug_index.get(loc_id),
            "province_id": province_id,
            "raw_material": loc.get("raw_material"),
            "is_port": bool(loc.get("port")),
            "holy_sites": loc.get("holy_sites"),  # list[int] or None
            "province_def":  province_def,
            "area":          chain["area"],
            "region":        chain["region"],
            "sub_continent": chain["sub_continent"],
            "continent":     chain["continent"],
        })

    return results


# ── Location Snapshot Rows ───────────────────────────────────────────────

def extract_location_snapshot_rows(save: EU5Save) -> list[dict]:
    """Extract per-owned-location snapshot data.

    Returns one dict per owned location.  ~13k rows for a mid-game save.
    Ownership is resolved from the country-side owned_locations list.
    """
    locs_db = save.raw.get("locations", {}).get("locations", {})
    owner_map = _build_owner_map(save)
    results: list[dict] = []

    for loc_id_str, loc in locs_db.items():
        if not isinstance(loc, dict):
            continue

        loc_id = int(loc_id_str)
        owner_info = owner_map.get(loc_id)
        if owner_info is None:
            continue

        # Integration data (list with one entry)
        integration_data = loc.get("integration_data")
        integration_type = None
        integration_owner_id = None
        if isinstance(integration_data, list) and integration_data:
            idata = integration_data[0]
            if isinstance(idata, dict):
                integration_type = idata.get("integration")
                integration_owner_id = idata.get("integration_owner")

        counters = loc.get("counters", {})
        if not isinstance(counters, dict):
            counters = {}

        owner_id = owner_info["owner_id"]
        owner_tag = owner_info["owner_tag"]

        results.append({
            "location_id": loc_id,
            # Ownership & Control
            "owner_id": owner_id,
            "owner_tag": owner_tag,
            "controller_id": loc.get("controller"),
            "previous_owner_id": loc.get("previous_owner"),
            "last_owner_change": loc.get("last_owner_change"),
            "last_controller_change": loc.get("last_controller_change"),
            "cores": loc.get("cores"),  # list[int] or None
            "garrison": loc.get("garrison"),
            "control": loc.get("control"),
            # Demographics & Culture
            "culture_id": loc.get("culture"),
            "secondary_culture_id": loc.get("secondary_culture"),
            "cultural_unity": loc.get("cultural_unity"),
            "religion_id": loc.get("religion"),
            "religious_unity": loc.get("religious_unity"),
            "language": loc.get("language"),
            "dialect": loc.get("dialect"),
            "pop_count": counters.get("Pops"),
            # Economic Geography
            "rank": loc.get("rank"),
            "development": loc.get("development"),
            "prosperity": loc.get("prosperity"),
            "tax": loc.get("tax"),
            "possible_tax": loc.get("possible_tax"),
            "market_id": loc.get("market"),
            "market_access": loc.get("market_access"),
            "value_flow": loc.get("value_flow"),
            "institutions": loc.get("institutions"),  # dict or None
            # Geopolitical Status
            "integration_type": integration_type,
            "integration_owner_id": integration_owner_id,
            "slave_raid_date": loc.get("slave"),
        })

    return results


# ── Province Statics ─────────────────────────────────────────────────────

def extract_province_statics(save: EU5Save) -> list[dict]:
    """Extract static metadata for all provinces."""
    prov_db = save.raw.get("provinces", {}).get("database", {})
    results: list[dict] = []

    for prov_id_str, prov in prov_db.items():
        if not isinstance(prov, dict):
            continue
        results.append({
            "id": int(prov_id_str),
            "province_definition": prov.get("province_definition"),
            "capital_location_id": prov.get("capital"),
        })

    return results


# ── Province Snapshot Rows ───────────────────────────────────────────────

def extract_province_snapshot_rows(save: EU5Save) -> list[dict]:
    """Extract per-owned-province snapshot data.

    Only provinces with an `owner` field are included (~4k rows).
    """
    prov_db = save.raw.get("provinces", {}).get("database", {})
    results: list[dict] = []

    for prov_id_str, prov in prov_db.items():
        if not isinstance(prov, dict) or prov.get("owner") is None:
            continue

        food = prov.get("food", {})
        if not isinstance(food, dict):
            food = {}

        results.append({
            "province_id": int(prov_id_str),
            "owner_id": prov.get("owner"),
            "food_current": food.get("current"),
            "food_max": prov.get("max_food_value"),
            "food_change_delta": prov.get("cached_food_change"),
            "trade_balance": prov.get("trade"),
            "goods_produced": prov.get("last_month_produced"),  # dict or None
        })

    return results


# ── Location Event Detection ─────────────────────────────────────────────

# State stored between snapshots: {loc_id: {field: value, ...}}
# Tracks: owner_id, controller_id, culture_id, religion_id, rank,
#         integration_type, cores (as frozenset), slave_raid_date

_EVENT_FIELDS = (
    "owner_id", "controller_id", "culture_id", "religion_id",
    "rank", "integration_type", "slave_raid_date",
)

_RANK_ORDER = {"rural_settlement": 0, "town": 1, "city": 2}

_INTEGRATION_ORDER = {"none": 0, "conquered": 1, "colonized": 2, "integrated": 3, "core": 4}


def detect_location_events(
    save: EU5Save,
    prev_state: dict[int, dict] | None,
) -> tuple[list[dict], dict[int, dict]]:
    """Compare current location state with previous to detect change events.

    Returns (event_dicts, new_state).  event_dicts are ready for insert_events.
    On first call (prev_state=None), builds state without emitting events.
    Ownership is resolved from the country-side owned_locations list.
    """
    locs_db = save.raw.get("locations", {}).get("locations", {})
    owner_map = _build_owner_map(save)
    game_date = save.game_date
    events: list[dict] = []
    new_state: dict[int, dict] = {}

    # Check all locations that are currently owned OR were previously owned
    all_loc_ids: set[int] = set(owner_map.keys())
    if prev_state:
        all_loc_ids |= set(prev_state.keys())

    for loc_id in all_loc_ids:
        loc = locs_db.get(str(loc_id))
        if not isinstance(loc, dict):
            loc = {}

        owner_info = owner_map.get(loc_id)
        owner_id = owner_info["owner_id"] if owner_info else None

        integration_data = loc.get("integration_data")
        integration_type = None
        if isinstance(integration_data, list) and integration_data:
            idata = integration_data[0]
            if isinstance(idata, dict):
                integration_type = idata.get("integration")

        cores = loc.get("cores")
        cores_set = frozenset(cores) if isinstance(cores, list) else frozenset()

        cur = {
            "owner_id": owner_id,
            "controller_id": loc.get("controller"),
            "culture_id": loc.get("culture"),
            "religion_id": loc.get("religion"),
            "rank": loc.get("rank"),
            "integration_type": integration_type,
            "slave_raid_date": loc.get("slave"),
            "cores": cores_set,
        }
        if owner_id is not None:
            new_state[loc_id] = cur

        if prev_state is None:
            continue

        prev = prev_state.get(loc_id)

        # New location (first ownership)
        if prev is None:
            if owner_id is not None:
                events.append({
                    "game_date": game_date,
                    "event_type": "location_first_owned",
                    "payload": {"location_id": loc_id, "owner_id": owner_id},
                })
            continue

        # Ownership change
        if cur["owner_id"] != prev["owner_id"]:
            events.append({
                "game_date": loc.get("last_owner_change", game_date),
                "event_type": "ownership_change",
                "payload": {
                    "location_id": loc_id,
                    "old_owner_id": prev["owner_id"],
                    "new_owner_id": cur["owner_id"],
                },
            })

        # Controller change
        if cur["controller_id"] != prev["controller_id"]:
            events.append({
                "game_date": loc.get("last_controller_change", game_date),
                "event_type": "controller_change",
                "payload": {
                    "location_id": loc_id,
                    "old_controller_id": prev["controller_id"],
                    "new_controller_id": cur["controller_id"],
                },
            })

        # Culture flip
        if cur["culture_id"] != prev["culture_id"]:
            events.append({
                "game_date": game_date,
                "event_type": "culture_flip",
                "payload": {
                    "location_id": loc_id,
                    "old_culture_id": prev["culture_id"],
                    "new_culture_id": cur["culture_id"],
                },
            })

        # Religion flip
        if cur["religion_id"] != prev["religion_id"]:
            events.append({
                "game_date": game_date,
                "event_type": "religion_flip",
                "payload": {
                    "location_id": loc_id,
                    "old_religion_id": prev["religion_id"],
                    "new_religion_id": cur["religion_id"],
                },
            })

        # Rank upgrade
        if cur["rank"] != prev["rank"]:
            cur_rank = _RANK_ORDER.get(cur["rank"], -1)
            prev_rank = _RANK_ORDER.get(prev["rank"], -1)
            if cur_rank > prev_rank:
                events.append({
                    "game_date": game_date,
                    "event_type": "rank_upgrade",
                    "payload": {
                        "location_id": loc_id,
                        "old_rank": prev["rank"],
                        "new_rank": cur["rank"],
                    },
                })

        # Integration upgrade
        if cur["integration_type"] != prev["integration_type"]:
            cur_int = _INTEGRATION_ORDER.get(cur["integration_type"] or "", -1)
            prev_int = _INTEGRATION_ORDER.get(prev["integration_type"] or "", -1)
            if cur_int > prev_int:
                events.append({
                    "game_date": game_date,
                    "event_type": "integration_upgrade",
                    "payload": {
                        "location_id": loc_id,
                        "old_type": prev["integration_type"],
                        "new_type": cur["integration_type"],
                    },
                })

        # Core gained / lost
        gained_cores = cur["cores"] - prev["cores"]
        lost_cores = prev["cores"] - cur["cores"]
        for cid in gained_cores:
            events.append({
                "game_date": game_date,
                "event_type": "core_gained",
                "payload": {"location_id": loc_id, "country_id": cid},
            })
        for cid in lost_cores:
            events.append({
                "game_date": game_date,
                "event_type": "core_lost",
                "payload": {"location_id": loc_id, "country_id": cid},
            })

        # Slave raid
        if cur["slave_raid_date"] and cur["slave_raid_date"] != prev.get("slave_raid_date"):
            events.append({
                "game_date": cur["slave_raid_date"],
                "event_type": "slave_raid",
                "payload": {
                    "location_id": loc_id,
                    "owner_id": cur["owner_id"],
                    "raid_date": cur["slave_raid_date"],
                },
            })

    return events, new_state
