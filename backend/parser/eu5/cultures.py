"""
cultures.py — Extract culture entity data from an EU5Save

Cultures are stored in culture_manager.database, keyed by numeric ID.
Each entry has a culture_definition (string key) which maps to a localised
display name via the loaded localisation dict.

Only static data is extracted — cultures have no meaningful dynamic snapshots
analogous to religion reform_desire or war scores.
"""

from __future__ import annotations

from typing import Any

from backend.parser.localisation import display_name
from backend.parser.save_loader import EU5Save


def extract_culture_statics(save: EU5Save) -> list[dict[str, Any]]:
    """
    Extract static culture data (one row per culture per playthrough).

    Returns a list of dicts with keys:
        culture_id, definition, name, culture_group
    """
    cm = save.raw.get("culture_manager", {}).get("database", {})
    results = []

    for cid_str, cdata in cm.items():
        if not isinstance(cdata, dict):
            continue

        definition = (
            cdata.get("culture_definition")
            or cdata.get("name")
            or f"culture_{cid_str}"
        )

        name = display_name(save.loc, definition) if save.loc else definition

        # culture_group may be a string key or absent
        group = cdata.get("culture_group", "")
        if not isinstance(group, str):
            group = ""

        results.append({
            "culture_id": int(cid_str),
            "definition": definition,
            "name": name,
            "culture_group": group,
        })

    return results
