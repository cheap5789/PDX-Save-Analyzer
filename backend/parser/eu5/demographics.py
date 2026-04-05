"""
demographics.py — Extract per-pop demographic data from an EU5 save

Each location stores a list of pop IDs in `location.population.pops`.
Each pop ID maps to a pop object in `population.database`.

Functions:
    extract_pop_snapshot_rows(save) → list[dict]  (~107k rows per mid-game save)
"""

from __future__ import annotations

import logging
from typing import Any

from backend.parser.save_loader import EU5Save

logger = logging.getLogger(__name__)


def extract_pop_snapshot_rows(save: EU5Save) -> list[dict]:
    """Extract per-pop demographic data for all owned locations.

    Iterates each owned location's `population.pops` list, resolves each
    pop ID in `population.database`, and extracts the tracked fields.

    Returns one dict per pop per location.  Typical volume: ~107k rows
    for a mid-game save (~13.6k locations × ~8 pops/location average).

    Pop objects that are non-dict sentinels (569 observed) are skipped.
    Locations with no `population.pops` key are skipped.
    """
    locs_db = save.raw.get("locations", {}).get("locations", {})
    pop_db = save.raw.get("population", {}).get("database", {})
    results: list[dict] = []

    for loc_id_str, loc in locs_db.items():
        if not isinstance(loc, dict) or loc.get("owner") is None:
            continue

        loc_id = int(loc_id_str)
        pop_section = loc.get("population")
        if not isinstance(pop_section, dict):
            continue

        pops_list = pop_section.get("pops")
        if not pops_list or not isinstance(pops_list, list):
            continue

        for pop_id in pops_list:
            pop_key = str(pop_id)
            pop = pop_db.get(pop_key)
            if not isinstance(pop, dict):
                continue

            results.append({
                "location_id": loc_id,
                "pop_id": pop_id,
                "type": pop.get("type", "unknown"),
                "estate": pop.get("estate"),
                "culture_id": pop.get("culture"),
                "religion_id": pop.get("religion"),
                "size": pop.get("size"),
                "status": pop.get("status"),  # None for slaves, some migrants
                "satisfaction": pop.get("satisfaction"),
                "intervention_satisfaction": pop.get("intervention_satisfaction"),
                "literacy": pop.get("literacy"),
                "owner_id": pop.get("owner"),  # present on tribesmen + some others
            })

    return results


def get_pop_summary_stats(rows: list[dict]) -> dict:
    """Compute summary statistics from extracted pop rows.

    Returns a dict with:
        total_pops: int
        total_size: float
        by_type: {type: {count, total_size, avg_satisfaction, avg_literacy}}
        by_status: {status: {count, total_size}}
        slave_count: int
        slave_size: float

    Useful for quick validation or summary display without DB.
    """
    from collections import defaultdict

    by_type: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_size": 0.0, "sat_sum": 0.0, "sat_n": 0, "lit_sum": 0.0, "lit_n": 0}
    )
    by_status: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_size": 0.0}
    )
    total_size = 0.0
    slave_count = 0
    slave_size = 0.0

    for r in rows:
        ptype = r.get("type", "unknown")
        status = r.get("status") or "None"
        size = r.get("size") or 0.0

        total_size += size

        bt = by_type[ptype]
        bt["count"] += 1
        bt["total_size"] += size
        if r.get("satisfaction") is not None:
            bt["sat_sum"] += r["satisfaction"]
            bt["sat_n"] += 1
        if r.get("literacy") is not None:
            bt["lit_sum"] += r["literacy"]
            bt["lit_n"] += 1

        bs = by_status[status]
        bs["count"] += 1
        bs["total_size"] += size

        if ptype == "slaves":
            slave_count += 1
            slave_size += size

    # Compute averages
    type_summary = {}
    for ptype, bt in by_type.items():
        type_summary[ptype] = {
            "count": bt["count"],
            "total_size": round(bt["total_size"], 4),
            "avg_satisfaction": round(bt["sat_sum"] / bt["sat_n"], 4) if bt["sat_n"] > 0 else None,
            "avg_literacy": round(bt["lit_sum"] / bt["lit_n"], 4) if bt["lit_n"] > 0 else None,
        }

    status_summary = {
        s: {"count": bs["count"], "total_size": round(bs["total_size"], 4)}
        for s, bs in by_status.items()
    }

    return {
        "total_pops": len(rows),
        "total_size": round(total_size, 4),
        "by_type": type_summary,
        "by_status": status_summary,
        "slave_count": slave_count,
        "slave_size": round(slave_size, 4),
    }
