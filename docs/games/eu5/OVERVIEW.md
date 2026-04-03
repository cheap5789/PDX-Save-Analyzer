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
| `stability` value 23.09 | `currency_data` | Stability — scale unknown (0–100?) | `common/defines/` |
| `karma` / `purity` / `righteousness` | `currency_data` | Religion-specific mechanics? | `common/religions/` or `common/defines/` |

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
