"""
religions.py — Extract religion entity data from an EU5Save

Religions are a parallel tracked entity type alongside countries.
Each snapshot records dynamic fields for religions that have them
(primarily major religions like Catholic with reform_desire, tithe, etc.).

Static fields (definition, group, color) are written once.
Dynamic fields (reform_desire, tithe, saint_power) are recorded per snapshot.
"""

from __future__ import annotations

from typing import Any

from backend.parser.save_loader import EU5Save


def extract_religion_statics(save: EU5Save) -> list[dict[str, Any]]:
    """
    Extract static religion data (written once per religion).

    Returns a list of dicts with keys:
        religion_id, definition, name, religion_group,
        has_religious_head, color_rgb
    """
    rm = save.raw.get("religion_manager", {}).get("database", {})
    results = []

    for rid_str, rdata in rm.items():
        if not isinstance(rdata, dict):
            continue

        definition = rdata.get("key") or rdata.get("definition", f"religion_{rid_str}")
        name = save.loc.get(definition, definition) if save.loc else definition
        color = rdata.get("color", {})
        color_rgb = color.get("rgb") if isinstance(color, dict) else None

        results.append({
            "religion_id": int(rid_str),
            "definition": definition,
            "name": name,
            "religion_group": rdata.get("group", ""),
            "has_religious_head": bool(rdata.get("has_religious_head", False)),
            "color_rgb": color_rgb,
        })

    return results


def extract_religion_snapshot_rows(save: EU5Save) -> list[dict[str, Any]]:
    """
    Extract per-religion dynamic data for one snapshot.

    Only emits rows for religions that have at least one non-null dynamic field.
    This keeps the table lean — most of the ~293 religions have no dynamic data.

    Returns a list of dicts with keys:
        religion_id, important_country, reform_desire, tithe,
        saint_power, timed_modifier_count
    """
    rm = save.raw.get("religion_manager", {}).get("database", {})
    results = []

    for rid_str, rdata in rm.items():
        if not isinstance(rdata, dict):
            continue

        reform_desire = rdata.get("reform_desire")
        tithe = rdata.get("tithe")
        saint_power = rdata.get("saint_power")
        important_country_raw = rdata.get("important_country")

        # Resolve important_country to TAG if it's a numeric ID
        important_country = None
        if important_country_raw is not None:
            if isinstance(important_country_raw, str):
                important_country = important_country_raw
            elif isinstance(important_country_raw, int):
                important_country = save.tag_index.get(
                    str(important_country_raw), str(important_country_raw)
                )

        # Count timed modifiers
        tm = rdata.get("timed_modifiers", {})
        timed_modifier_count = 0
        if isinstance(tm, dict):
            tm_list = tm.get("timed_modifiers", [])
            if isinstance(tm_list, list):
                timed_modifier_count = len(tm_list)

        # Only emit if at least one dynamic field is populated
        if any(v is not None for v in [reform_desire, tithe, saint_power, important_country]):
            results.append({
                "religion_id": int(rid_str),
                "important_country": important_country,
                "reform_desire": reform_desire,
                "tithe": tithe,
                "saint_power": saint_power,
                "timed_modifier_count": timed_modifier_count,
            })

    return results
