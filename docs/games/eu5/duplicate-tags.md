# Duplicate TAGs in EU5 Saves

**Status:** Discovered 2026-04-09 during Territory tab backfill work.
**Decision:** Drop `UNIQUE(playthrough_id, tag)` on the `countries` table and use `country_id` as the sole primary handle for country identity. `owner_tag` in `location_snapshots` is retained as a denormalised display hint but is **not** a join key.

---

## Finding

The common assumption `countries.tags[numeric_id] → TAG` is **not injective** in EU5 save files. Multiple distinct country objects can share the same 3-letter TAG inside a single save, and the game itself tolerates this without conflict.

Empirically, four such collisions were observed in the Bavaria autosave used for development (`saves/autosave MP bavaria.eu5`):

| TAG | `country_id` pair | Pattern |
|-----|-------------------|---------|
| YMT | 606 / 607         | Formable + pre-existing slot |
| YUA | 756 / 2337        | Plain Yuán + Northern Yuán (horde split) |
| SWI | 2159 / 2160       | Plain SWI + formable Swiss Confederacy (from BRN) |
| OTC | 33556827 / 33556872 | Otchigin + horde civil-war pretender |

All eight objects carry `country_type="Real"`, their own `currency_data`, `score`, and `capital` — they are fully-alive country entities, not rebel shells or debris. All are mapped to their shared TAG via the top-level `countries.tags` dict, so `save.tag_index` (which is built from that dict) returns the same TAG for both IDs in each pair.

## Two observed collision patterns

### Pattern A — formable + pre-existing slot

The *formable* variant has been activated (e.g. `SWI_f` formed from BRN) and carries a richer payload: `previous_tags`, `formed_from`, ~80 keys. The *pre-existing slot* with the same TAG still exists in the same save with a slimmer ~37-key payload. Examples: SWI, YMT, YUA.

> The save retains a second "alive" entity under the same TAG slot as the formable. This is expected game behaviour — the formable does not overwrite or merge with the pre-existing object.

### Pattern B — horde civil-war pretender

During a horde civil war the game spawns a pretender country that inherits the parent TAG as a display base. The pretender's `country_name` is a dict with a localisation override:

```
country_name = {
  name:  "horde_civil_war_pretender_country",
  key:   { Adjective: "horde_civil_war_pretender_country_adjective" },
  bases: { Base: "OTC" }
}
```

The renderer resolves this to the pretender's override name, but the `tags` map still points the pretender's `country_id` at the parent TAG.

## Consequences for the schema

The `countries` table previously asserted `UNIQUE(playthrough_id, tag)`. Under that constraint, `extract_country_rows()` hit `IntegrityError` during bulk upsert because it produced one row per `country_id` and two rows for each duplicate TAG. The failed insert rolled back all uncommitted writes in the same transaction (locations, location_snapshots), producing the confusing "cultures populated but locations empty" symptom that triggered this investigation.

## Decision

1. **Primary key stays** `PRIMARY KEY(playthrough_id, country_id)` — country_id is the real, unambiguous handle.
2. **Drop** `UNIQUE(playthrough_id, tag)`. Index on `tag` is retained (non-unique) for lookups that *do* want to group by display tag.
3. **`location_snapshots.owner_id`** (already present) is the canonical foreign link to a country. `owner_tag` is kept as a denormalised convenience for display and tag-level filters but is **not** authoritative when two countries share a TAG.
4. **Joins** from `location_snapshots` to `countries` go through `owner_id → country_id`, never through `owner_tag → tag`.

## Consequences for existing features

- **Demographics tab predecessor stitching** (`get_pop_snapshots(owner_tags=[...])`) currently filters by `location_snapshots.owner_tag IN (...)`. For a duplicate-tag pair this will include pops owned by *both* country objects under that TAG. This is a pre-existing bug surfaced by the finding, not introduced by this change. It is not fixed here; see "Open questions" below.
- **`canonical_tag` finalisation** in the DB (`finalize_country_canonical_tags`) walks the `prev_tags → tag` graph. With duplicate tags, the walk can pick the "wrong" row when the target TAG has two rows. The fix is to walk by `country_id` when possible, falling back to tag only for predecessor stubs (which by definition have no `country_id` in the save). Tracked below.
- **Territory tab** (Phase B/C of the current work) will join by `owner_id → country_id`, which is safe under this model.

## Open questions

1. **Predecessor stitching by country_id.** The current `prev_tags` succession model is tag-based. To make it duplicate-tag-safe, `prev_tags` would need to become `prev_country_ids` (numeric) — but the save only exposes predecessors as TAG strings, not IDs. For predecessors that no longer exist in the save (absorbed countries), there is no `country_id` to point to. This remains a tag-based lookup by necessity.
2. **Canonical tag for duplicate-tag entities.** Should both SWI rows share `canonical_tag="SWI"`, or should the formable variant's canonical_tag be something disambiguating (e.g. `SWI#2160`)? For now both share the same canonical_tag — the ambiguity is pushed to the UI which can show "Switzerland (2160)" when there is a collision.
3. **Display name for pattern B pretenders.** When `country_name` is a dict with a `bases.Base` field, the parser currently stores just the TAG. It should resolve the override name (e.g. "Northern Yuán") and store it as the country's `name`. Tracked as a follow-up in `countries.py`.

## References

- `backend/parser/eu5/countries.py` — `extract_country_rows()` (deduplication discussion)
- `backend/parser/save_loader.py` line 181–183 — `tag_index` construction (non-injective)
- `backend/storage/database.py` — `countries` table definition
- Bavaria autosave (`saves/autosave MP bavaria.eu5`) — 4 duplicate-tag pairs verified 2026-04-09
