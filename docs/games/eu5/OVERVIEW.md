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

All culture and religion references in `pop_snapshots`, `location_snapshots`, and `location_snapshots` are stored as **INTEGER IDs** (raw from save). Dedicated reference tables provide ID → display name resolution:

- **`cultures` table**: populated from `culture_manager.database` each backfill pass. Columns: `id` (int), `definition` (string key), `name` (localised display name), `culture_group`.
- **`religions` table**: populated from `religion_manager.database`. Columns: `id`, `definition`, `religion_group`, `has_religious_head`, colour, and per-snapshot dynamic fields in `religion_snapshots`.

Both tables are fetched once per playthrough by the frontend into `GameLocalizationContext`, which exposes `fmtCulture(id)`, `fmtReligion(id)`, and `fmtEstate(key)` helpers. All tabs (DemographicsTab, TerritoryTab, ReligionsTab) use these helpers so that integer IDs never appear in the UI.

### Country Succession Chains (implemented 2026-04-07)

When a country is formed (e.g. Spain formed from Castile + Aragon), the successor stores the absorbed TAGs in `countries.database[id].previous_tags`. The parser reads this into a `countries` table:

- `prev_tags` (JSON array): predecessor TAGs this country was formed from.
- `canonical_tag` (computed): terminal successor in the chain. Set to self on first write; `finalize_country_canonical_tags()` walks predecessor chains after full backfill to propagate the correct value.

**Why this matters:** The Demographics tab uses `canonical_tag` to group a country and all its predecessors when filtering by country — so selecting "Spain" automatically includes Castile and Aragon's historical territory.

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
