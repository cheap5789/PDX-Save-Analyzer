# Duplicate TAGs in EU5 Saves

**Status:** Discovered 2026-04-09 during Territory tab backfill work. Revised 2026-04-09 after empirical verification.
**Governing principle:** *"If a country identifies as this TAG, then it is this tag."* Same-tag collisions in the save are ghost artifacts, not legitimate coexistence — only one entry per tag is live; the others are dormant shells that should be ignored.
**Decision:** Drop `UNIQUE(playthrough_id, tag)` on the `countries` table as a safety net, but resolve same-tag groups **in the extractor** so the constraint would not be violated in practice either. Joins still go through `country_id`, never `tag`.

---

## Finding

EU5 pre-allocates a database entry for every possible country tag — a dormant "shell" with a ~37-key payload, no `owned_locations`, and no `previous_tags`. When a formable activates (e.g. `SWI_f` is formed from BRN), the game creates a **new** `country_id` for the real entity and leaves the original shell sitting in the database untouched. The result: two distinct `country_id`s share the same TAG in `countries.tags`, and the common assumption `countries.tags[numeric_id] → TAG` is **not injective**.

Empirically, four such collisions were observed in the Bavaria autosave used for development (`saves/autosave MP bavaria.eu5`):

| TAG | ghost `country_id` | live `country_id` | owned locs | Notes |
|-----|--------------------|--------------------|------------|-------|
| YMT | 607 (shell)        | 606 (`prev_tags=['STC']`) | 0 | Live entity owns no territory — annexed or currently landless, but still a valid succession node |
| YUA | 756 (shell)        | 2337 (`prev_tags=['CHI']`, Northern Yuán) | 17 | |
| SWI | 2159 (shell)       | 2160 (`prev_tags=['BRN']`, Swiss Confederacy) | 44 | |
| OTC | 33556872 (shell)   | 33556827 (shell, kept by determinism rule) | 0 | Neither sibling is live — both are shells; the lowest `country_id` is kept arbitrarily |

**Important correction:** an earlier version of this document framed these as "legitimate co-existing same-tag countries." That was wrong. The project rule, confirmed by the user, is that tags are a unique identifier in the UI / script layer and two live countries cannot share one. The duplicates are therefore always ghost + live (or, rarely, ghost + ghost), never live + live.

## Ghost-slot filter (implemented in `extract_country_rows`)

The filter groups all country rows by tag, then resolves any group with more than one entry:

1. An entry is classified as **real** if it has `owned_locations` (non-empty) OR `previous_tags` (non-empty). Otherwise it is a **shell**.
2. If the group contains at least one real entry, **drop every shell** in the group.
3. If the group contains only shells (the OTC case), **keep the lowest `country_id`** (deterministic) and drop the rest.

This filter runs during parser extraction, before any DB write. Verified against the Bavaria autosave: zero duplicate tags in the output.

Groups with a single entry are untouched — the filter only applies where a collision actually exists. Dormant tag shells for countries that have no collision remain in the table as they always did; they are inert and carry no cost.

## Why the old pretender framing was wrong

The initial finding document contained a section called "Pattern B — horde civil-war pretender" that claimed the pretender was a separate live entity sharing the parent TAG. On closer inspection the horde civil-war pretender uses the dict-form `country_name = { name: "horde_civil_war_pretender_country", bases: { Base: "OTC" } }` mechanism for its **display name override**, which is a different concern (localisation resolution) and does not imply a second live `country_id`. The OTC collision observed in the save is two shells that never activated, not a live pretender and a live Otchigin. Display-name resolution for dict-form `country_name` entries is tracked separately (see Item 3 / Pattern-B work in `countries.py`).

## Consequences for the schema

The `countries` table previously asserted `UNIQUE(playthrough_id, tag)`. Under that constraint, `extract_country_rows()` hit `IntegrityError` during bulk upsert because — before the ghost filter existed — it produced one row per `country_id` and therefore two rows for each duplicate TAG. The failed insert rolled back all uncommitted writes in the same transaction (locations, location_snapshots), producing the confusing "cultures populated but locations empty" symptom that triggered this investigation.

With the ghost-slot filter in place, the extractor no longer produces same-tag duplicates, so the constraint **could** be safely reinstated. We leave it off anyway as a belt-and-braces defence against a future save exhibiting a collision pattern we have not yet catalogued — the ghost filter is a parser-level contract, the constraint would be a storage-level one, and they would duplicate the same invariant from two directions.

## Decision

1. **Primary key stays** `PRIMARY KEY(playthrough_id, country_id)` — country_id is the real, unambiguous handle.
2. **Drop** `UNIQUE(playthrough_id, tag)`. Index on `tag` is retained (non-unique) for lookups that *do* want to group by display tag.
3. **Ghost-slot filter** runs in `extract_country_rows` before rows reach the DB; dormant shells that collide with a live entry are dropped.
4. **`location_snapshots.owner_id`** (already present) is the canonical foreign link to a country. `owner_tag` is kept as a denormalised convenience for display and tag-level filters.
5. **Joins** from `location_snapshots` to `countries` go through `owner_id → country_id`, never through `owner_tag → tag`.

## Consequences for existing features

- **Demographics tab predecessor stitching** (`get_pop_snapshots(owner_tags=[...])`) filters by `location_snapshots.owner_tag IN (...)`. With the ghost filter this is now unambiguous — only one `country_id` per tag survives — so the tag-based lookup is safe.
- **`canonical_tag` finalisation** in the DB (`finalize_country_canonical_tags`) walks the `prev_tags → tag` graph. With the ghost filter, each tag resolves to exactly one row, so the walk is deterministic.
- **Territory tab** joins by `owner_id → country_id`, which is safe under this model.

## Open questions

1. **Predecessor stitching by country_id.** The current `prev_tags` succession model is tag-based. To make it fully `country_id`-safe, `prev_tags` would need to become `prev_country_ids` (numeric) — but the save only exposes predecessors as TAG strings, not IDs. For predecessors that no longer exist in the save (absorbed countries), there is no `country_id` to point to. This remains a tag-based lookup by necessity, and is now unambiguous because of the ghost filter.
2. **~~Dict-form display name resolution (Pattern-B work)~~.** *Resolved 2026-04-09.* Implemented as `EU5Save.resolve_country_display_name()` in `backend/parser/save_loader.py`. The resolution chain: (a) unwrap `country_name` dict-form to pull out the inner `name`, (b) try the regular loc dict, (c) fall back to the scripted loc dict and substitute `$VAR$` tokens via `resolve_scripted_value`, (d) fall back to the tag's loc display name. Scripted entries come from `load_scripted_localisation`, which walks the localisation tree recursively so that entries defined in `events/**/flavor_*_l_english.yml` (e.g. `NORTHERN_YUA: "Northern $YUA$"`) are discoverable. `horde_civil_war_pretender_country` with `$ADJ$` substitution is also handled via the `bases.Base` hint → `{TAG}_ADJ` lookup. Verified on the Bavaria autosave: YUA 2337 resolves to "Northern Yuán", CHI 761 to "Chén", OTC/YMT/SWI to their loc names.
3. **`AAA*` colonial placeholder countries.** ~65 live colonial placeholder countries have `country_name` set to a raw province slug (e.g. `sumbawa_province`). Many of those slugs are themselves loc keys ("Sumbawa", "Surrey", "Erāq-e Ajam"), so the display name resolver **would** have silently rendered them as bare place names. That bypasses the intended "colony of X"-style display rule which is still TBD. Per the deferral agreed on 2026-04-09, the resolver hard-guards on `tag.startswith("AAA")` and returns the tag fallback until the colonial rule is implemented. Remove the guard as part of that future work.

## References

- `backend/parser/eu5/countries.py` — `extract_country_rows()`: ghost-slot filter implementation (3-pass: classify → resolve groups → emit)
- `backend/parser/save_loader.py` — `tag_index` construction (non-injective; caller must dedupe)
- `backend/storage/database.py` — `countries` table definition (no `UNIQUE(playthrough_id, tag)`)
- Bavaria autosave (`saves/autosave MP bavaria.eu5`) — 4 duplicate-tag pairs verified and resolved 2026-04-09
