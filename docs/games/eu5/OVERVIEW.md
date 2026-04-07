# EU5 — Game Overview

> This document grows as we discover and verify game concepts via base game config files.
> **Rule:** Nothing is documented here without a cited config file or verified source.

---

## Game Version Tested
- **1.1.10** (from autosave sample)

## Save File
- See [`save-schema.md`](save-schema.md) for the complete format analysis.

---

## Verified Concepts

### Numeric ID Resolution (verified 2026-04-03)

The save is **self-referential** for culture and religion IDs. No external config files needed for parsing:

| ID type | Lookup location in save JSON | Example |
|---------|------------------------------|---------|
| Culture | `culture_manager.database[id]` → string key | `1066` → `"bavarian"` |
| Religion | `religion_manager.database[id]` → string key | `12` → `"catholic"` |
| Country tag | `countries.tags[id]` → 3-letter TAG | `2186` → `"WUR"` |

External localisation files are only needed for **display names** (e.g. `"bavarian"` → `"Bavarian"`, `"WUR"` → `"Württemberg"`).

### Culture & Religion Reference Tables (implemented 2026-04-07)

All culture and religion references in `pop_snapshots` and `location_snapshots` are stored as **INTEGER IDs** (raw from save). Dedicated reference tables provide ID → display name resolution:

- **`cultures` table**: populated from `culture_manager.database` each backfill pass. Columns: `id` (int), `definition` (string key), `name` (localised display name), `culture_group`.
- **`religions` table**: populated from `religion_manager.database`. Columns: `id`, `definition`, `religion_group`, `has_religious_head`, colour, and per-snapshot dynamic fields in `religion_snapshots`.

Both tables are fetched once per playthrough by the frontend into `GameLocalizationContext`, which exposes `fmtCulture(id)`, `fmtReligion(id)`, and `fmtEstate(key)` helpers. All tabs (DemographicsTab, TerritoryTab, ReligionsTab) use these helpers so that integer IDs never appear in the UI.

> **Schema note (fixed 2026-04-07):** The `religions` table originally used `id INTEGER PRIMARY KEY` (SQLite global rowid). When two playthroughs shared the same religion id (e.g. Catholic = id 12), the second playthrough's INSERT failed on the rowid constraint *before* the `ON CONFLICT(playthrough_id, id)` handler could fire — silently leaving the religions table empty for that playthrough and causing the UI to display raw IDs like `religion_12`. Fixed by using a composite `PRIMARY KEY (playthrough_id, id)`, matching the `cultures` table pattern. DB must be wiped and repopulated after this change.

### Proportional Time Axis in Charts (implemented 2026-04-07)

EU5 saves are created manually and at irregular intervals, so the gaps between snapshots can span weeks or decades of in-game time. Rendering a categorical X axis (one column per save, equal width) makes a 32-year gap look the same as a 3-month gap — distorting trends visually.

All time-series charts use a **proportional linear X axis**: each save date is converted to a fractional year value and Recharts renders gaps proportionally to actual elapsed time.

**Conversion (`euDateToNum`, `frontend/src/utils/formatters.js`):**

```js
// "1514.7.1" → 1514.500,  "1482.4.15" → 1482.272
function euDateToNum(dateStr) {
  const [year, month = 1, day = 1] = dateStr.split('.').map(Number)
  return year + (month - 1) / 12 + (day - 1) / 365
}
```

**Chart pattern** (used in `DemographicsTab.jsx` and `ReligionsTab.jsx`):
- Add `dateNum: euDateToNum(d.game_date)` to each data point alongside the original `date` string.
- Sort data by `dateNum` (not lexicographically by date string).
- Use `<XAxis dataKey="dateNum" type="number" scale="linear" domain={['dataMin','dataMax']} tickFormatter={fmtYearTick} />`.
- Use `labelFormatter={(_v, payload) => payload?.[0]?.payload?.date ?? ''}` on `<Tooltip>` to show the original game date string (e.g. `"1514.7.1"`) rather than the numeric value.

### Country Succession Chains (implemented 2026-04-07)

When a country is formed (e.g. Spain formed from Castile + Aragon), the successor stores the absorbed TAGs in `countries.database[id].previous_tags`. The parser reads this into a `countries` table:

- `prev_tags` (JSON array): predecessor TAGs this country was formed from.
- `canonical_tag` (computed): terminal successor in the chain. Set to self on first write; `finalize_country_canonical_tags()` walks predecessor chains after full backfill to propagate the correct value.

**Why this matters:** The Demographics tab uses `canonical_tag` to group a country and all its predecessors when filtering by country — so selecting "Spain" automatically includes Castile and Aragon's historical territory.

### Geographic Hierarchy & Location Slugs (implemented 2026-04-07)

EU5 organises space as a six-level tree:

```
continent → sub_continent → region → area → province_definition → location
```

- **Location → slug** is fully self-referential in the save: `metadata.compatibility.locations` is an array indexed by `location_id - 1` whose entries are the slug strings (e.g. id `1` → `"stockholm"`). No game files required.
- **Location → province_id** comes from the save (`locations.locations[id].province`).
- **Province → province_definition** comes from the save (`provinces.database[id].definition`, e.g. `"uppland_province"`).
- **The five upper levels** (`province_definition` → `area` → `region` → `sub_continent` → `continent`) are **not** in the save. They live in `<EU5 install>/game/map_data/definitions.txt`, a flat tab-indented `name = { ... }` tree where each leaf province block lists its location slugs as bare tokens.

`backend/parser/eu5/geography_index.py` parses `definitions.txt` once per pipeline/backfill session via `GeographyIndex.load(game_install_path)` and exposes `chain_for_location(slug)` / `chain_for_province(slug)`. Per project rule #5, the file is read at runtime from the user's install path and never shipped. Smoke test against the verified install: 9 continents, 23 sub_continents, 82 regions, 803 areas, 4309 province_definitions, 28573 locations.

The chain is denormalised onto each row in the `locations` table (`slug`, `province_def`, `area`, `region`, `sub_continent`, `continent`) with indexes on `continent` and `region`, so per-continent / per-region rollups are cheap.

Display names live in the geography YAML files (`location_names_l_<lang>.yml`, `province_names_l_<lang>.yml`, `area_names_l_<lang>.yml`, `region_names_l_<lang>.yml`, `continent_l_<lang>.yml`). `backend/parser/localisation.py::load_geo_localisation()` loads them into a `{level → {slug → display_name}}` map; `GET /api/geography/{playthrough_id}` intersects that with the slugs actually used by the playthrough so the payload only contains what the UI needs. The frontend exposes `fmtLocation`, `fmtProvince`, `fmtArea`, `fmtRegion`, `fmtSubContinent`, `fmtContinent` on `GameLocalizationContext`, each falling back to a cleaned slug if no display name is loaded.

> **Known gap (deferred, lowest priority):** EU5 ships ~62 `location_names_<culture>_l_english.yml` files providing per-culture renamings. The base file resolves only ~8116 of the 28573 location slugs; the per-culture files cover most of the rest. Until those are loaded, many locations will display as a cleaned-up slug rather than their proper culture-specific name.

### Location Ownership (verified 2026-04-07)

In EU5, ownership is declared on the **country** object, not the location:

```
countries.database.{country_id}.owned_locations = [loc_id, ...]
```

The location object does carry an `owner` field in many cases, but it can be absent or stale. The parser builds an inverted map (`_build_owner_map()`) from the country-side list before processing locations. **Do not read ownership from `locations.locations[id].owner` directly** — use the owner map.

### Localisation (verified 2026-04-04)

| Item | Detail |
|------|--------|
| Location | `<EU5 install>/game/main_menu/localization/<language>/` |
| Format | `.yml` files, one per domain (e.g. `countries_l_english.yml`) |
| Entry count | ~86,507 entries (English) |
| Entry format | `  KEY: "Display Name"` (indented, quoted value) |
| Languages | Subfolders of `localization/`: `english`, `french`, `german`, etc. (auto-detected at runtime) |

### Age Definitions (verified 2026-04-04)

| Item | Detail |
|------|--------|
| Config path | `<EU5 install>/game/common/age/` |
| Save key | `current_age` (e.g. `"age_3_discovery"`) |

### Game Install Structure (verified 2026-04-04)

Default Steam path: `C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`

| Resource | Path (relative to install) |
|----------|---------------------------|
| Config files | `game/` → `common/`, `events/`, `setup/` |
| Localisation | `game/main_menu/localization/<language>/` |

---

## Discovered But Unverified

| Observed string | Context | Likely meaning | Config file needed |
|----------------|---------|----------------|--------------------|
| `hundred_years_war.200_fire_only_once` | string_lookup | An event flag | `events/` |
| `flavor_sco.101_fire_only_once` | string_lookup | Scotland flavor event flag | `events/` |
| `pattern_quarterly_flag.dds` | CoA data | Flag pattern texture | `gfx/coat_of_arms/patterns/` |
| `stability` value 23.09 | `currency_data` | Stability — scale −100 to +100, confirmed via `common/auto_modifiers/country.txt` | Resolved — see save-schema.md |
| `karma` / `purity` / `righteousness` | `currency_data` | Religion-specific mechanics — confirmed: `karma`=Buddhist, `purity`=Shinto, `righteousness`=Sanjiao | Resolved — see save-schema.md |

---

## Config Files — Known Locations

| Category | Path (relative to `<install>/game/`) | Status |
|----------|--------------------------------------|--------|
| Ages/Eras | `common/age/` | ✅ Verified |
| Localisation | `main_menu/localization/<language>/` | ✅ Verified |
| Countries | `common/countries/` | Exists, not yet explored |
| Country tags | `common/country_tags/` | Exists, not yet explored |
| Cultures | `common/cultures/` | Exists, not yet explored |
| Religions | `common/religions/` | Exists, not yet explored |
| Technologies | `common/technologies/` | Exists, not yet explored |
| Setup (day-0 state) | `setup/` | Exists, not yet explored |
| Events | `events/` | Exists, not yet explored |
| Defines | `common/defines/` | Needs verification |

> **Note:** Path `common/age/` (singular) — not `common/ages/` as assumed from EU4 conventions.
