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

## Placeholder-tag countries (`AAA*` / `ABA*`)

**Status:** Investigated and resolved 2026-04-09. Supersedes the earlier "colonial placeholder" framing, which was empirically wrong.

### What they actually are

EU5 pre-allocates a range of three-letter-plus-digit tags — `AAA00`..`AAA99` and `ABA00`..`ABA99` — as generic slots for auto-generated minor independent nations. In the Bavaria autosave there are **95 live `AAA*` + 10 live `ABA*` = 105 placeholder countries**. They are:

- `country_type == "Real"` with a capital, primary culture, ruler, full government, and independent diplomatic relations.
- **Not** subjects of anyone. An exhaustive grep of the 320 MB rakaly JSON for `overlord`, `subject_type`, `colonial_parent`, `liege`, `master_id`, `is_subject`, `sovereign`, `suzerain`, and `subjects` found zero hits on any `AAA*`/`ABA*` record.
- Four of them (highest: `AAA82` at 190.40/mo) carry non-zero `last_months_subject_tax`, meaning they *collect* subject tax — they are overlords, not subjects. That inversion alone rules out the "colonial subject" hypothesis.
- Typologically they are tribes, petty kingdoms, and dynastic fragments scattered across the map to fill regions that vanilla doesn't hand-author.

The earlier "Spanish colony of X" framing was based on a wrong premise and has been removed from this document, from `save_loader.py`, and from `save-schema.md`.

### Naming convention

Each placeholder country stores `country_name` as a **plain string** — a raw location slug from the game's `location_names_l_english.yml`. Examples: `sumbawa_province`, `surrey_province`, `kurmysh_province`, `mahadeo`, `zemetchino`. The slug is the country's de-facto name — the location it sits on or is named after.

Resolution falls out naturally from step 2 of `EU5Save.resolve_country_display_name()`: the slug is looked up in `self.loc`, which now includes `location_names/location_names_l_english.yml` thanks to the explicit second source added to `load_localisation` on 2026-04-09 (see that function's docstring). All 105 placeholder countries resolve via this path; no prefix-specific code is required.

### Known collisions

Two pairs of placeholder countries resolve to the same display name in the Bavaria autosave:

- `AAA64` and `AAA70` → both "Borisoglebsk"
- `AAA78` and `AAA84` → both "Penza"

Decision (2026-04-09): **accept the collisions**. The UI already decorates duplicate display names with the tag suffix (`"Borisoglebsk (AAA64)"` vs `"Borisoglebsk (AAA70)"`), which is sufficient disambiguation. Joins remain on `country_id`, so the collision is purely cosmetic.

### Prefix allowlist

The set of known placeholder-tag prefixes is a **documentation-only allowlist**: `{AAA, ABA}`, applied **only to suffixed tags** (`AAA00`..`AAA99`, `ABA00`..`ABA99`). The bare three-letter tags `AAA` and `ABA` are **not** placeholders — in particular `ABA` is a live country called **Alba** with `country_name == "ABA"` (self-referential plain-string override resolving to `loc["ABA"] = "Alba"`). The resolver does not implement a code-level prefix check; the allowlist is strictly for writeup and mental model. If a future save surfaces a new prefix family (`ACA*`, `BAA*`, ...), the resolver will still handle it correctly as long as the slug is in `loc`, but this document should be updated to record the discovery.

### Loader note: `location_names_l_english.yml`

The canonical location-name file lives at `main_menu/localization/english/location_names/location_names_l_english.yml` (29,791 lines). It is **not** reachable by the default top-level glob in `load_localisation`; we explicitly pull it in by name. The per-culture/per-language variants in the same directory (`location_names_polish_l_english.yml`, etc.) carry dotted keys like `anyksciai.west_slavic_language: "…"` and are deferred to a later phase (original agreement 2026-04-07). Do not "helpfully" make the loader recursive without revisiting that decision.

### Regex relaxation side-effect

To parse `location_names_l_english.yml` at all, `_LINE_RE` was relaxed from `^\s+` (at least one leading whitespace) to `^\s*` (zero or more). That file contains ~thousands of entries at column 0, violating Paradox's own indentation convention. Side-effect: the relaxed regex picks up col-0 entries in other loc files too, widening the loaded dicts:

- `save.loc`: 86,689 → 120,629 entries (+33,940)
- `save.scripted_loc`: 13,327 → 15,322 entries (+1,995)

This was a deliberate widening (decision 2026-04-09, option A over special-casing the single file) on the principle that col-0 entries exist in real game files and refusing to parse them is the bug, not the fix. No regressions observed on spot-checked country display names (YUA, CHI, OTC, YMT, SWI, FRA, WUR, SWE, DAN) or on the ghost-filter winners.

## Open questions

1. **Predecessor stitching by country_id.** The current `prev_tags` succession model is tag-based. To make it fully `country_id`-safe, `prev_tags` would need to become `prev_country_ids` (numeric) — but the save only exposes predecessors as TAG strings, not IDs. For predecessors that no longer exist in the save (absorbed countries), there is no `country_id` to point to. This remains a tag-based lookup by necessity, and is now unambiguous because of the ghost filter.
2. **~~Dict-form display name resolution (Pattern-B work)~~.** *Resolved 2026-04-09.* Implemented as `EU5Save.resolve_country_display_name()` in `backend/parser/save_loader.py`. The resolution chain: (a) unwrap `country_name` dict-form to pull out the inner `name`, (b) try the regular loc dict, (c) fall back to the scripted loc dict and substitute `$VAR$` tokens via `resolve_scripted_value`, (d) fall back to the tag's loc display name. Scripted entries come from `load_scripted_localisation`, which walks the localisation tree recursively so that entries defined in `events/**/flavor_*_l_english.yml` (e.g. `NORTHERN_YUA: "Northern $YUA$"`) are discoverable. `horde_civil_war_pretender_country` with `$ADJ$` substitution is also handled via the `bases.Base` hint → `{TAG}_ADJ` lookup. Verified on the Bavaria autosave: YUA 2337 resolves to "Northern Yuán", CHI 761 to "Chén", OTC/YMT/SWI to their loc names.
3. **~~`AAA*` colonial placeholder countries~~.** *Resolved 2026-04-09.* See "Placeholder-tag countries (`AAA*` / `ABA*`)" above. They are not colonial subjects; the previous "Spanish colony of X" framing was empirically wrong.

## References

- `backend/parser/eu5/countries.py` — `extract_country_rows()`: ghost-slot filter implementation (3-pass: classify → resolve groups → emit)
- `backend/parser/save_loader.py` — `tag_index` construction (non-injective; caller must dedupe)
- `backend/storage/database.py` — `countries` table definition (no `UNIQUE(playthrough_id, tag)`)
- Bavaria autosave (`saves/autosave MP bavaria.eu5`) — 4 duplicate-tag pairs verified and resolved 2026-04-09
