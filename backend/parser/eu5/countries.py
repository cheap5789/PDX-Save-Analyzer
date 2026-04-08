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

    Ghost-slot filter (same-tag collision resolution):
        EU5 pre-allocates a shell database entry for every possible tag.
        When a formable activates (e.g. YUA is formed from CHI), a NEW
        country_id with the real data is created while the original shell
        lingers — producing two rows sharing the same tag. Per the project
        rule "if it identifies as this TAG, it is this tag," we collapse
        same-tag groups: within any group of >1 entries sharing a tag, we
        drop pure shells (no owned_locations AND no previous_tags) whenever
        at least one "real" sibling exists. If all siblings in a group are
        shells (e.g. a formable that never activated AND has a duplicate
        shell), we keep the lowest country_id for determinism.
        See docs/games/eu5/duplicate-tags.md for the empirical finding.

    Fields per row:
        country_id (int): numeric game ID
        tag (str):        3-letter TAG
        name (str|None):  localised display name (None if no localisation loaded)
        prev_tags (list): predecessor TAGs this country was formed from
    """
    countries_db = save.raw.get("countries", {}).get("database", {})
    rows: list[dict] = []
    seen_tags: set[str] = set()

    # --- Pass 1: group country_ids by tag and classify each entry ---
    # Entry classification: "real" = has territory or succession history;
    # "shell" = pre-allocated dormant slot with neither.
    from collections import defaultdict
    tag_groups: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    # list of (country_id_str, is_real) per tag
    for country_id_str, cdata in countries_db.items():
        if not isinstance(cdata, dict):
            continue
        tag = save.tag_index.get(country_id_str)
        if not tag:
            continue
        owned = cdata.get("owned_locations")
        has_territory = isinstance(owned, list) and len(owned) > 0
        prev_raw = cdata.get("previous_tags")
        has_succession = bool(prev_raw)
        is_real = has_territory or has_succession
        tag_groups[tag].append((country_id_str, is_real))

    # --- Pass 2: resolve same-tag collisions to ghost-id set ---
    ghost_ids: set[str] = set()
    for tag, entries in tag_groups.items():
        if len(entries) <= 1:
            continue  # no collision, nothing to filter
        real_entries = [cid for cid, is_real in entries if is_real]
        if real_entries:
            # Drop every non-real (shell) sibling
            for cid, is_real in entries:
                if not is_real:
                    ghost_ids.add(cid)
        else:
            # All shells — keep lowest country_id (numeric), drop the rest
            def _numeric(cid_str: str) -> int:
                try:
                    return int(cid_str)
                except (TypeError, ValueError):
                    return 2**31
            sorted_ids = sorted((cid for cid, _ in entries), key=_numeric)
            for cid in sorted_ids[1:]:
                ghost_ids.add(cid)

    # --- Pass 3: emit rows, skipping ghosts ---
    for country_id_str, cdata in countries_db.items():
        if not isinstance(cdata, dict):
            continue
        if country_id_str in ghost_ids:
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

        # Display name: prefer the override-aware resolver which handles
        # dict-form country_name (Pattern-B, e.g. horde civil war pretender),
        # plain string overrides (e.g. CHI → "CHE" → "Chén"), and scripted
        # templates (e.g. YUA 2337 → "NORTHERN_YUA" → "Northern $YUA$" →
        # "Northern Yuán"). Falls back to the tag-based lookup for plain
        # cases and for AAA* colonial placeholders (deferred rule). See
        # docs/games/eu5/duplicate-tags.md for the full resolution chain.
        name: str | None = None
        if save.loc:
            resolved = save.resolve_country_display_name(country_id, fallback_tag=tag)
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
