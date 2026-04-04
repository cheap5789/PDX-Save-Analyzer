"""
snapshot.py — Extract a snapshot dict from an EU5Save

A snapshot is a dict of field values for one or more countries at a point
in time.  The set of extracted fields is controlled by an enabled-fields
list (selected by the user per campaign).

The snapshot dict is what gets JSON-serialised into the `snapshots.data`
column in SQLite.

Output shape:
{
    "game_date": "1482.1.1",
    "game_version": "1.1.10",
    "current_age": "age_3_discovery",
    "countries": {
        "WUR": {"gold": 251.7, "manpower": 3.6, ...},
        "SWE": {"gold": 100.3, "manpower": 5.1, ...},
        ...
    }
}
"""

from __future__ import annotations

from typing import Any

from backend.parser.save_loader import EU5Save
from backend.parser.eu5.field_catalog import FieldDef, resolve_field_value, get_default_fields


def extract_snapshot(
    save: EU5Save,
    enabled_fields: list[FieldDef] | None = None,
    country_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Extract a snapshot from an EU5Save.

    Args:
        save:            Parsed save object.
        enabled_fields:  Which fields to extract.  Defaults to catalog defaults.
        country_tags:    Which country TAGs to extract.
                         None = all Real countries.  Pass a list to limit
                         (e.g. ["WUR", "SWE", "FRA"]).

    Returns:
        A snapshot dict ready for JSON serialisation.
    """
    if enabled_fields is None:
        enabled_fields = get_default_fields()

    # Build the list of (country_id, tag, country_data) to extract
    if country_tags is not None:
        # Invert tag_index to find IDs for requested tags
        tag_to_id: dict[str, str] = {v: k for k, v in save.tag_index.items()}
        targets: list[tuple[str, str, dict]] = []
        for tag in country_tags:
            cid = tag_to_id.get(tag)
            if cid is not None:
                cdata = save.country_data(cid)
                if cdata:
                    targets.append((cid, tag, cdata))
    else:
        targets = save.all_real_countries()

    # Extract fields for each country
    countries: dict[str, dict[str, Any]] = {}
    for cid, tag, cdata in targets:
        row: dict[str, Any] = {}
        for field in enabled_fields:
            val = resolve_field_value(cdata, field)
            if val is not None:
                row[field.key] = val
        if row:
            countries[tag] = row

    return {
        "game_date": save.game_date,
        "game_version": save.game_version,
        "current_age": save.current_age_key,
        "countries": countries,
    }
