"""
countries.py — Extract country reference rows from an EU5 save.

The country reference table (countries) stores a stable, per-playthrough
mapping of numeric country IDs → TAGs, with succession chain data
(prev_tags, canonical_tag) so that UI components can transparently
"stitch" Castile and Spain into one continuous entity.
"""

from __future__ import annotations

from backend.parser.save_loader import EU5Save


def extract_country_rows(save: EU5Save) -> list[dict]:
    """Return one dict per country for bulk_upsert_countries.

    Includes both Real countries and non-Real former countries (e.g. Castile
    after Spain is formed) so that the succession chain stays complete.
    For-each country with prev_tags, stub rows are also emitted for any
    predecessor TAGs that might not appear in this save's database (covering
    the edge case where a predecessor was removed after formation).

    Fields per row:
        country_id (int): numeric game ID
        tag (str):        3-letter TAG
        name (str|None):  localised display name (None if no localisation loaded)
        prev_tags (list): predecessor TAGs this country was formed from
    """
    countries_db = save.raw.get("countries", {}).get("database", {})
    rows: list[dict] = []
    seen_tags: set[str] = set()

    for country_id_str, cdata in countries_db.items():
        if not isinstance(cdata, dict):
            continue
        tag = save.tag_index.get(country_id_str)
        if not tag:
            continue

        prev_tags_raw = cdata.get("previous_tags")
        if isinstance(prev_tags_raw, str) and prev_tags_raw:
            prev_tags: list[str] = [prev_tags_raw]
        elif isinstance(prev_tags_raw, list):
            prev_tags = [t for t in prev_tags_raw if isinstance(t, str)]
        else:
            prev_tags = []

        try:
            country_id = int(country_id_str)
        except (TypeError, ValueError):
            continue

        name: str | None = None
        if save.loc:
            resolved = save.country_display_name(tag)
            name = resolved if resolved and resolved != tag else None

        rows.append({
            "country_id": country_id,
            "tag": tag,
            "name": name,
            "prev_tags": prev_tags,
        })
        seen_tags.add(tag)

    # Emit stub rows for predecessor TAGs not in this save's database.
    # These are tags that appear in some country's prev_tags but have no
    # own database entry (e.g. CAS after Spain is formed and CAS is purged).
    # We use a negative pseudo-ID based on tag hash so they don't clash.
    for row in list(rows):
        for old_tag in row["prev_tags"]:
            if old_tag not in seen_tags:
                pseudo_id = -(hash(old_tag) & 0x7FFFFFFF)  # stable negative int
                rows.append({
                    "country_id": pseudo_id,
                    "tag": old_tag,
                    "name": None,
                    "prev_tags": [],
                })
                seen_tags.add(old_tag)

    return rows
