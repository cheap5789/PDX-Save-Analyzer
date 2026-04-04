# EU5 Save File — Format Documentation

> All findings in this document are empirically derived from analyzing an actual EU5 autosave file.
> Game version: **1.1.10**
> Nothing here is assumed — only observed.

---

## File Identification

- **Extension:** `.eu5`
- **Magic header:** `SAV0203` (first 7 bytes, ASCII)
- **Format family:** Paradox Jomini binary token format (same engine as CK3, Victoria 3, HOI4)
- **Encoding:** Binary (NOT plaintext Clausewitz — unlike EU4 non-Ironman saves)

> ⚠️ **Important:** EU5 saves are binary-encoded by default, even in non-Ironman mode. This differs from EU4, where non-Ironman saves were plaintext. Do NOT attempt direct text parsing.

---

## Overall File Structure

The `.eu5` file is a **composite format** with two distinct sections:

```
┌─────────────────────────────────┐
│  SECTION 1: Pre-ZIP Header      │  ~395 KB
│  Binary Jomini token data       │
│  Mixed with some Clausewitz     │
│  plaintext (coat of arms, etc.) │
├─────────────────────────────────┤
│  SECTION 2: ZIP Archive         │  ~34 MB compressed
│  ├── gamestate                  │  136.4 MB uncompressed (76% compression)
│  └── string_lookup              │  3.4 MB uncompressed  (50% compression)
└─────────────────────────────────┘
```

### Section 1 — Pre-ZIP Header (~395 KB)

- Starts immediately at byte 0 with magic `SAV0203`
- Contains Jomini binary token data for save metadata
- Observed fields (from readable strings): save UUID, country name, game version, save type ("Autosave"), coat of arms data
- Coat of arms data appears to be stored in plaintext Clausewitz format embedded within the binary stream
- **ZIP starts at byte offset: 404,380**

### Section 2 — ZIP Archive

The ZIP occupies the rest of the file. It contains exactly two entries:

#### `gamestate`
- **Uncompressed size:** 142,980,201 bytes (136.4 MB)
- **Compressed size:** ~34 MB (76% compression ratio)
- **Format:** Jomini binary token format
- **Content:** Main game state — all country data, provinces, characters, wars, etc.
- Starts with the same binary token pattern as the pre-ZIP header

#### `string_lookup`
- **Uncompressed size:** 3,508,503 bytes (3.4 MB)
- **Compressed size:** ~1.76 MB (50% compression ratio)
- **Format:** Binary list of length-prefixed UTF-8 strings
- **Content:** Dynamic string values used in the save (event IDs, flavor strings, etc.)
- String encoding: each entry is `[u16 length][UTF-8 bytes]` (little-endian)
- Observed values: event IDs like `age_3_discovery`, `flavor_sco.101_fire_only_once`, `hundred_years_war.200_fire_only_once`, country/character names, etc.
- **Purpose:** In the Jomini binary format, "unknown" or dynamic strings are stored by index; this table provides the mapping from index → actual string value

---

## Jomini Binary Token Format

The `gamestate` (and pre-ZIP header) use the Jomini binary token encoding:

- **Keys** are encoded as 16-bit unsigned integers (tokens), e.g., `0x09de`
- **Values** follow immediately, typed via a preceding type byte
- **Known tokens** (built-in game keys like `"treasury"`, `"manpower"`, etc.) require a token lookup table supplied by the game or Rakaly
- **Unknown tokens** (dynamic strings) reference the `string_lookup` table by index
- **Observed type markers** (preliminary, unverified): `0x0003` (object open?), `0x000e` (bool?), `0x000f` (string?), `0x000c` (float?)

> ⚠️ Type marker meanings are NOT confirmed. Do not use these until verified against rakaly source or game token definitions.

---

## Parsing Chain

```
.eu5 file
  │
  └─ rakaly CLI json <file> → JSON stdout  ✅ Confirmed working (v0.8.14)
```

Rakaly handles the full pipeline internally: ZIP extraction, binary token decoding, string_lookup resolution.
No manual ZIP extraction or custom token decoding needed.

---

## Observed Metadata (from sample autosave)

| Field | Value | Source |
|-------|-------|--------|
| Game version | 1.1.10 | Pre-ZIP header, readable string |
| Save type | Autosave | Pre-ZIP header, readable string |
| Save UUID | c832299a-d810-47d8-a21a-3e5e710c98d9 | Pre-ZIP header |
| Player country | Upper Bavaria | Pre-ZIP header, readable string |
| Country tag color | #dc5a8326 | Pre-ZIP header (CoA data) |

---

---

## Rakaly CLI — Verified Working ✅

**rakaly v0.8.14** successfully decodes `.eu5` saves and outputs clean JSON via:
```
rakaly json <file.eu5>
```
Output goes to stdout. Parsing time for a 34.5 MB save (136 MB uncompressed): fast (< 2s).

---

## Top-Level JSON Structure (empirically discovered)

| Key | Type | Notes |
|-----|------|-------|
| `metadata` | dict(13) | Save metadata — see below |
| `start_of_day` | string | Current game date e.g. `"1482.1.1"` |
| `current_age` | string | e.g. `"age_3_discovery"` — needs config file to label |
| `speed` | int | Game speed setting |
| `countries` | dict(2) | Has `tags` (id→tag) and `database` (id→country object) |
| `provinces` | dict(1) | Has `database` (id→province object) |
| `character_db` | dict(2) | Has `database` (id→character object) |
| `population` | dict(2) | Has `database` (id→pop object) and `needed` list |
| `war_manager` | dict(2) | Has `names` list and `database` (id→war object) |
| `situation_manager` | dict(22) | Named situations (black_death, colonial_revolution, etc.) |
| `diplomacy_manager` | dict(2446) | Diplomatic relations |
| `played_country` | dict(7) | Player session info — see below |
| `religion_manager` | dict(4) | Religion state |
| `culture_manager` | dict(1) | Culture state |
| `market_manager` | dict(2) | Trade/market state |
| `dynasty_manager` | dict(1) | Dynasties |
| `disease_outbreak_manager` | dict(2) | Disease outbreaks |
| `event_manager` | dict(3) | Fired events |
| `counters` | dict(51) | Global game counters |

---

## `metadata` Object

| Key | Type | Sample value | Notes |
|-----|------|-------------|-------|
| `date` | string | `"1482.1.1"` | Current in-game date |
| `playthrough_id` | string | UUID | Unique save identifier |
| `playthrough_name` | string | `"Upper Bavaria #dc5a8326"` | Player-visible game name |
| `save_label` | string | `"Autosave"` | Save type |
| `version` | string | `"1.1.10"` | Game version |
| `player_country_name` | string | `"Upper Bavaria"` | Display name of player country |
| `multiplayer` | bool | `true` | |
| `incompatible` | bool | `true` | Save made with mods/different version |
| `flag` | string | Clausewitz text block | CoA definition for player country |
| `enabled_dlcs` | list | `["Shared DLC Data"]` | |

---

## `played_country` Object

| Key | Sample value | Notes |
|-----|-------------|-------|
| `name` | `"Capitaine Erin"` | Player's character/ruler name |
| `id` | `4` | Player slot ID |
| `country` | `2186` | Numeric ID into `countries.database` |
| `player_proficiency` | `"EXPERT"` | |
| `same_name` | `true` | |

---

## `countries` Object

Two sub-keys:

- **`tags`**: `{numeric_id: "TAG", ...}` — e.g. `{3: "SWE", 4: "DAN", 2186: "WUR"}`
- **`database`**: `{numeric_id: country_object, ...}`

### Country Object — Key Fields

> ⚠️ `country_name` is the 3-letter TAG (e.g. `"WUR"`), NOT the display name.
> Display name requires localisation files. Only `metadata.player_country_name` gives the player's display name directly.

**`currency_data`** sub-object (main tracked resources):

| Key | Sample (WUR) | Semantic (unverified — needs config) |
|-----|-------------|--------------------------------------|
| `gold` | 251.70 | Treasury |
| `manpower` | 3.60 | Manpower pool |
| `stability` | 23.09 | Stability (scale unknown — needs config) |
| `inflation` | 0.00023 | Inflation |
| `prestige` | 75.70 | Prestige |
| `army_tradition` | 41.24 | Army tradition |
| `government_power` | 80.36 | Government power |
| `karma` | -58.67 | Karma (religion-related?) |
| `religious_influence` | 49.18 | Religious influence |
| `purity` | 60 | Purity |
| `righteousness` | 90 | Righteousness |

**`balance_history_2`** sub-object (monthly deltas — note PascalCase keys):

| Key | Sample (WUR) |
|-----|-------------|
| `Gold` | +20.21/month |
| `Manpower` | +0.07/month |
| `Stability` | +0.12/month |
| `WarExhaustion` | -0.09/month |
| `Inflation` | +0.00001/month |
| `Prestige` | -0.64/month |
| `ArmyTradition` | -0.006/month |
| `GovernmentPower` | -0.45/month |
| `Karma` | +0.30/month |
| `ReligiousInfluence` | +0.55/month |
| `Complacency` | -0.07/month |

**`score`** sub-object:

| Key | Notes |
|-----|-------|
| `score_place` | Overall rank (861 for WUR) |
| `score_rating.ADM/DIP/MIL` | Score value per category |
| `score_rank.ADM/DIP/MIL` | Rank per category |

**Simple top-level fields on country object**:

| Key | Sample | Notes |
|-----|--------|-------|
| `country_type` | `"Real"` | "Real" / "Pirates" / "Mercenaries" |
| `estimated_monthly_income` | 40.28 | Total estimated monthly income |
| `estimated_monthly_income_trade_and_tax` | 29.06 | Income from trade + tax |
| `monthly_trade_balance` | -0.04 | Net trade balance |
| `monthly_trade_value` | 14.71 | Gross trade value |
| `current_tax_base` | 93.18 | Current tax base |
| `potential_tax_base` | 145.06 | Potential tax base |
| `monthly_manpower` | 0.039 | Manpower gain/month |
| `last_month_gold_income` | 38.59 | Actual gold income last month |
| `max_manpower` | 4.458 | Max manpower |
| `total_produced` | 214.62 | Total goods produced |
| `primary_culture` | 1066 | Numeric ID — needs config file |
| `primary_religion` | 12 | Numeric ID — needs config file |
| `great_power_rank` | 116 | Great power ranking |
| `capital` | 1388 | Numeric location ID |
| `last_months_population` | 431.28 | Total population |
| `last_months_tax_income` | 28.06 | Tax income last month |
| `last_months_army_maintenance` | 6.12 | Army upkeep last month |
| `last_months_fort_maintenance` | 3.72 | Fort upkeep last month |
| `last_months_building_maintenance` | 14.07 | Building upkeep last month |
| `starting_technology_level` | 3 | Starting tech level |
| `naval_range` / `colonial_range` | 1250 | Range values |

---

## `provinces` Object

Sub-key `database`: `{numeric_id: province_object}`

### Province Object — Key Fields (sample)

| Key | Sample | Notes |
|-----|--------|-------|
| `capital` | 1 (location ID) | Capital location |
| `province_definition` | `"uppland_province"` | Config key — needs config file |
| `owner` | 3 (country ID) | Owning country |
| `max_food_value` | 1700 | Max food capacity |
| `cached_food_change` | -2.02 | Food change per tick |
| `trade` | 2.02 | Trade value |

---

## `character_db` Object

Sub-key `database`: `{numeric_id: character_object}`

### Character Object — Key Fields

| Key | Sample | Notes |
|-----|--------|-------|
| `country` | 3 (country ID) | Owning country |
| `script` | `"swe_birger_jarl"` | Script ID — links to character definition |
| `first_name` | `"name_birger"` | Localisation key — needs loc file |
| `adm` | 97 | Administrative skill |
| `dip` | 54 | Diplomatic skill |
| `mil` | 91 | Military skill |
| `children` | list of IDs | Children character IDs |
| `father` | character ID | Father's ID |
| `religion` | 12 (numeric) | Religion ID — needs config file |

---

## `situation_manager` Object

Named situations, each with status + dates:

| Key | Status (sample) | Notes |
|-----|----------------|-------|
| `black_death` | `after` (1346–1357) | Historical plague |
| `fall_of_delhi` | `after` (1344–1421) | |
| `guelphs_and_ghibellines` | `after` (1337–1391) | |
| `colonial_revolution` | `[]` (not triggered) | |
| `columbian_exchange` | `[]` (not triggered) | |
| `council_of_trent` | `[]` (not triggered) | |

---

## Resolved Questions

- [x] **Culture/religion numeric IDs:** The save is **self-referential**. `culture_manager.database[id]` and `religion_manager.database[id]` contain the int→string key mapping directly. No external config files needed for parsing — only for display names. Confirmed 2026-04-03.
- [x] **Country display names:** Resolved via localisation `.yml` files at `<EU5 install>/game/main_menu/localization/<language>/`. The key is the 3-letter TAG (e.g. `WUR`), the localisation provides the display name (e.g. "Württemberg"). Confirmed 2026-04-04.
- [x] **Age definitions:** Found at `common/age/` (not `common/ages/`). Age keys like `age_3_discovery` are defined there. Confirmed 2026-04-04.
- [x] **EU5 base game install directory:** Default Steam path is `C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V`. Config files under `game/`, localisation under `game/main_menu/localization/`. Confirmed 2026-04-04.

---

## Data Quality Audit — Field-by-Field

> Systematic review of every field we extract, verified against game UI.
> For each field: raw JSON path, raw value, what we store in DB, what we display in frontend, and any transformation needed.
> Reference save: Greenland playthrough, autosave at 1345.10.1, game version 1.1.10.
> Reference country: France (tag `FRA`, country ID `1135`) — a great power with all field types populated.

### Identity & Metadata

| # | Field | JSON Path (relative to country object) | Raw Value (FRA) | Store in DB | Display in Frontend | Status | Notes |
|---|-------|---------------------------------------|-----------------|-------------|--------------------|---------| ------|
| 1 | Country tag | `country_name` / `definition` | `"FRA"` | `FRA` | Localise via `FRA` → "France" | **OK** | `country_name`, `definition`, `flag`, `historical` all contain the same tag string. Only `country_name` needs storing. Localisation source: `localization/<lang>/countries_l_<lang>.yml` |
| 2 | Country type | `country_type` | `"Real"` | `Real` | Not displayed | **OK** | Filter for "real" countries vs rebel/colonial shell entities. Always `"Real"` for player-relevant countries. |
| 3 | Entity type | `type` | `"location"` | `location` | Not displayed | **NEEDS FIX** | Determines what kind of entity the country is. Possible values: `location` (land-controlling societies — the standard case), `building` (entities existing through buildings on others' land, e.g. banks), `pop` (societies without government), `army` (mercenaries), `navy` (pirates). Only `location`-type countries should get full field extraction (economy, military, diplomacy, etc.). Non-location types should only store minimal data: population, gold. |
| 4 | Court language | `court_language` | `"french_language"` | `french_language` | Localise → "French" | **NOT TRACKED** | Visible in game UI. Localisation source: `localization/<lang>/cultural_and_languages_l_<lang>.yml`. Not currently extracted by summary or snapshot. |
| 5 | Liturgical language | `liturgical_language` | `"latin_language"` | `latin_language` | Localise → "Latin" | **NOT TRACKED** | Same localisation source as court language. Not currently extracted. Lower priority — only relevant for religion mechanics. |
| 6 | Nickname | `nickname` | `["subunit_nickname_french_royal"]` | — | — | **SKIP** | Refers to a unit regiment nickname, NOT a country nickname. Not useful for country-level tracking. |
| 7 | Color | `color.rgb` | `[33, 33, 173]` | `[33,33,173]` | Chart/map line color | **NOT TRACKED** | Direct RGB array. Useful for frontend chart colors (match country's map color). Not currently extracted. |
| 8 | Primary culture | `primary_culture` | `1021` (int) | `french` (string key) | Localise `french` → "French" | **OK** | Resolved via `culture_manager.database[1021].name` → `"french"`. Store string key, not int ID. Currently handled in `summary.py`. |
| 9 | Primary religion | `primary_religion` | `12` (int) | `catholic` (string key) | Localise `catholic` → "Catholic" | **OK** | Resolved via `religion_manager.database[12].definition` → `"catholic"`. Store string key, not int ID. Currently handled in `summary.py`. |
| 10 | Accepted cultures | `accepted_cultures` | `[1026, 1025, 1034, ...]` (9 ints) | List of string keys: `["champenais","picard","poitevin",...]` | Localise each | **NOT TRACKED** | Each int resolves via `culture_manager.database[id].name`. Game shows 4 culture statuses per country: primary, accepted, tolerated, discriminated. We should track which cultures have which status. |
| 11 | Tolerated cultures | `tolerated_cultures` | `[1037, 1035, 1031, 1032]` (4 ints) | List of string keys | Localise each | **NOT TRACKED** | Same resolution as accepted_cultures. Discriminated = all other cultures present in country's pops but not in any of the above lists. |
| 12 | Capital | `capital` | `2179` (location ID) | `2179` (int) | Localise → "Paris" | **PARTIAL** | Currently stored as raw int. Resolution chain: location ID → game setup files (NOT in save) map location ID → string key (e.g. `"paris"`) → localisation via `localization/<lang>/location_names/location_names_l_<lang>.yml`. Province via `locations.locations[2179].province` → `1087` → `provinces.database[1087].province_definition` = `"pays_france_province"` (but this is NOT the city name). |
| 13 | Great power flag | `great_power` | `True` | `true` | "Great Power" | **NOT TRACKED** | Boolean. Not currently in summary or snapshot. Could be derived from `great_power_rank` but explicit flag is cleaner. |
| 14 | Great power rank | `great_power_rank` | `4` | `4` | "#4" | **OK** | Integer rank. Currently tracked in summary.py and field_catalog.py. |
| 15 | Government type | `government.type` | `"monarchy"` | `monarchy` | Localise → "Monarchy" | **NOT TRACKED** | Not currently extracted. Useful for event detection (government type changes). Localisation source: `localization/<lang>/government_l_<lang>.yml` (needs verification). |
| 16 | Succession law | `government.heir_selection` | `"salic_law"` | `salic_law` | Localise → "Salic Law" | **NOT TRACKED** | Not currently extracted. Lower priority. |

#### Identity & Metadata — Backlog

Changes to apply after full audit is complete:

1. **[BUG] Capital display**: Capital is stored as raw int `2179` but cannot be resolved to a display name from the save alone. Location name resolution requires parsing game setup files (e.g. `common/locations/` or map definitions) to build a `location_id → string_key` mapping, then localising via `location_names_l_<lang>.yml`. **Decision needed**: parse game setup files at startup, or store raw ID only?

2. **[NEW] Culture status tracking**: Add culture status (primary/accepted/tolerated/discriminated) to country summary. Currently only `primary_culture` is tracked. `accepted_cultures` and `tolerated_cultures` are lists of culture IDs on the country object. Discriminated = cultures present in country's pops but not in any of the three lists. This requires cross-referencing population data.

3. **[NEW] Country color**: Extract `color.rgb` from country object and include in snapshot/summary. Useful for frontend to match chart line colors to the country's in-game map color.

4. **[NEW] Government type**: Extract `government.type` from country object. Track in summary for event detection (e.g. revolution changes government type).

5. **[LOW] Court language**: Extract `court_language`. Localise via `cultural_and_languages_l_<lang>.yml`. Low priority unless user wants to track language shifts.

6. **[CLEANUP] Redundant fields**: `definition`, `flag`, `historical` all duplicate `country_name`. Only `country_name` (= TAG) needs to be read. `historical` could be interesting if a country was formed (tag changed) but this is edge-case.

7. **[BUG] Entity type filtering**: Currently we filter on `country_type == "Real"` but ignore `type`. Non-location entities (building/pop/army/navy) pass the "Real" filter but have fundamentally different data shapes. Full field extraction (military, diplomacy, stability, etc.) is meaningless for them. Fix: check `type` field during extraction. For `location` entities → full extraction. For `building`, `pop`, `army`, `navy` → store only minimal data (population, gold). Skip them from event diffing, charts, and most analyses.

### Economy — currency_data (resource pools)

`currency_data` holds the current stock of each resource currency. All values are floats.

| # | Field | JSON Path | Raw (FRA) | Game UI (FRA) | Unit / Scale | Transform | Catalog key | Status | Notes |
|---|-------|-----------|-----------|---------------|-------------|-----------|-------------|--------|-------|
| 17 | Treasury | `currency_data.gold` | `353.22` | 353.22 | Gold (ducats). Direct value. | None | `gold` | **OK** | |
| 18 | Manpower | `currency_data.manpower` | `0.839` | 839 | Raw value is in thousands. Multiply ×1000 for display. | ×1000 | `manpower` | **NEEDS FIX** | Currently stored raw. Must multiply ×1000 before storing or at display time. Absent on small countries (e.g. Greenland has no `manpower` in currency_data). |
| 19 | Sailors | `currency_data.sailors` | `0.026` | 26 | Raw value is in thousands. Multiply ×1000 for display. | ×1000 | — | **NOT TRACKED** | Same ×1000 factor as manpower. Not in field catalog. Should add. |
| 20 | Stability | `currency_data.stability` | `6.88` | 6 | Scale: −100 to +100, displayed with 2 decimals in game (shown as integer in overview, full precision in tooltip). | None (store raw, display rounded or full) | `stability` | **OK** | Confirmed: −100 to 100 scale. Three auto-modifiers exist in `common/auto_modifiers/country.txt`: `stability_impact` (full range), `positive_stability_impact` (0 to 100 only), `negative_stability_impact` (−100 to 0 only). |
| 21 | Inflation | `currency_data.inflation` | `0.209` | 20.90% | Raw is a 0–1 fraction. Multiply ×100 for percentage display. | ×100 for display | `inflation` | **NEEDS FIX** | Currently stored raw (0.209). Frontend should display as "20.9%". Either transform at storage or at display time. |
| 22 | Prestige | `currency_data.prestige` | `26.01` | 26.01 | Direct value. | None | `prestige` | **OK** | |
| 23 | Army Tradition | `currency_data.army_tradition` | `8.72` | 8.72% | Displayed as percentage in game but raw value IS the percentage (not a 0–1 fraction). | None (just add "%" in display) | `army_tradition` | **OK** | Value is already the percentage. No multiplication needed, just suffix "%" in frontend. |
| 24 | Navy Tradition | `currency_data.navy_tradition` | `0.10` | 0.10% | Same as army tradition — raw value is the percentage. | None (add "%" in display) | — | **NOT TRACKED** | Not in field catalog. Should add. |
| 25 | Government Power | `currency_data.government_power` | `53.27` | 53.27 | Direct value. Scale 0–100. | None | `government_power` | **OK** | |
| 26 | Karma | `currency_data.karma` | `-40.80` | — (not shown for Catholics) | Religion-specific currency. Present in save even if not used by current religion. | None | `karma` | **OK** | Not displayed for Catholic countries. Keeping it tracked — value may become relevant on religion conversion. |
| 27 | Religious Influence | `currency_data.religious_influence` | `39.14` | 39.14 | Direct value. | None | `religious_influence` | **OK** | |
| 28 | Purity | `currency_data.purity` | `60` | — (not shown for Catholics) | Religion-specific. Present in save even if not used by current religion. | None | `purity` | **OK** | Same as karma — tracked but may not be visible in UI for all religions. |
| 29 | Righteousness | `currency_data.righteousness` | `90` | — (not shown for Catholics) | Religion-specific. Same as above. | None | `righteousness` | **OK** | |
| 30 | Complacency | `currency_data.complacency` | `7.70` | 7.7 | Scale: 0 to 100. Over 90 triggers a monthly chance of complacency disaster lasting decades. Reduced by diplomatic spending, being target of a coalition, and having threatening rivals. | None | — (only monthly tracked) | **NEEDS FIX** | Currently we only track `balance_history_2.Complacency` (the monthly delta) but NOT the stock value. Must add `currency_data.complacency` to the field catalog — the absolute level is crucial gameplay info (staying under 90). |
| 31 | War Exhaustion | `currency_data.war_exhaustion` | (present on countries at war) | — | Direct value. | None | — (only monthly tracked) | **CHECK** | FRA has no `war_exhaustion` in currency_data in this save (not at war?). Currently tracked only as monthly delta via `balance_history_2.WarExhaustion`. Need to check: should we also track the stock? |

#### Economy currency_data — Backlog

8. **[BUG] Manpower ×1000**: `currency_data.manpower` raw value is in thousands. Value `0.839` = 839 manpower in game. Must apply ×1000 transform. Decision: apply at storage time (store `839`) or at display time? Recommendation: store raw, transform in frontend — keeps DB values faithful to save.

9. **[NEW] Sailors**: Add `currency_data.sailors` to field catalog. Same ×1000 factor as manpower. Key: `sailors`, category: `military`, display: "Sailors".

10. **[BUG] Inflation ×100**: `currency_data.inflation` raw value is a 0–1 fraction. Value `0.209` = 20.9% in game. Must apply ×100 for percentage display. Same decision as manpower: store raw, display transformed.

11. **[NEW] Navy Tradition**: Add `currency_data.navy_tradition` to field catalog. Key: `navy_tradition`, category: `military`, display: "Navy Tradition".

12. **[NEW] Complacency stock**: Add `currency_data.complacency` to field catalog (the absolute value, not just the monthly delta). Key: `complacency`, category: `stability`, display: "Complacency". Critical gameplay threshold at 90.

13. **[CHECK] War Exhaustion stock**: Verify whether `currency_data.war_exhaustion` should be tracked as a stock value alongside the existing monthly delta. Only present on countries currently at war.

### Economy — Income & Expenses

Reference: France (FRA) at 1345.10.1 — budget screen verified against game UI.

#### Income Fields

| # | Field | JSON Path | Raw (FRA) | Game UI | Keep? | Status | Notes |
|---|-------|-----------|-----------|---------|-------|--------|-------|
| 32 | Total income | `economy.income` | `80.81` | 80.81 | **YES** | **OK** | Current month's total income. Matches game budget screen. |
| 33 | Estimated monthly income | `estimated_monthly_income` | `80.54` | — | **NO** | **SKIP** | Projection — slightly differs from actual. Redundant with `economy.income`. |
| 34 | Last month gold income | `last_month_gold_income` | `84.12` | — | **NO** | **SKIP** | Previous month's income. Can be reconstructed from `economy.monthly_gold` history. |
| 35 | Estimated trade+tax income | `estimated_monthly_income_trade_and_tax` | `37.58` | — | **NO** | **SKIP** | Projection. Not needed alongside actuals. |
| 36 | Tax income | `last_months_tax_income` | `27.48` | 27.48 | **YES** | **OK** | Actual tax income. Matches game. Good for P&L breakdown. |
| 37 | Subject tax base | `last_months_subject_tax` | `454.87` | 454.86 | **YES** | **OK** | Displayed in game as "Wealth of the Subjects" — this is the tax base, not income. Variable name is misleading but value checks out. |
| 38 | Trade value | `monthly_trade_value` | `66.58` | — | **YES** | **OK** | Gross trade value — interesting for trade analysis. |
| 39 | Trade balance | `monthly_trade_balance` | `1.67` | — | **YES** | **OK** | Net trade balance (trade income minus outflows). |
| 40 | Coin minting | `economy.coin_minting` | `0.11` | — | **YES** | **OK** | Income from minting. |
| — | Food sold | ??? | NOT FOUND | +3.62 | **YES** | **MISSING** | Game shows food sold as an income line item. Not found in extracted JSON. May be calculated at runtime by the game engine or stored in a structure not yet identified. |

#### Expense Fields

| # | Field | JSON Path | Raw (FRA) | Game UI | Keep? | Status | Notes |
|---|-------|-----------|-----------|---------|-------|--------|-------|
| 41 | Total expense | `economy.expense` | `58.86` | 58.86 | **YES** | **OK** | Current month's total expense. Matches game. |
| 42 | Army maintenance | `last_months_army_maintenance` | `5.36` | 5.36 | **YES** | **OK** | |
| 43 | Navy maintenance | `last_months_navy_maintenance` | `0.21` | 0.21 | **YES** | **NOT TRACKED** | Not currently in field catalog. Must add. |
| 44 | Fort maintenance | `last_months_fort_maintenance` | `28.87` | 28.87 | **YES** | **OK** | |
| 45 | Building maintenance | `last_months_building_maintenance` | `17.12` | 17.12 | **YES** | **OK** | |
| 46 | Manpower expense | `last_months_manpower_expense` | `0.01` | — | **NO** | **SKIP** | Not displayed in game UI. Unclear meaning. |
| 47 | Sailor expense | `last_months_sailor_expense` | `0.001` | — | **NO** | **SKIP** | Not displayed in game UI. Unclear meaning. |
| — | Interest on loans | ??? | NOT FOUND | 2.22 | **YES** | **MISSING** | Game shows interest paid on loans (FRA has 362.72 total debt). Not found as a dedicated field. May be calculated from loan objects. |
| — | Building subsidies | ??? | NOT FOUND | 0.23 | **YES** | **MISSING** | Game shows building subsidies expense. Not found in extracted JSON. |
| — | Court cost | ??? | NOT FOUND | 0 | **YES** | **MISSING** | Game shows cost of the court. Currently 0 for FRA. Not found in extracted JSON. |
| — | Food bought | ??? | NOT FOUND | -10.47 | **YES** | **MISSING** | Game shows food bought from market as expense. Not found in extracted JSON. May be calculated at runtime. |

**Expense gap analysis**: Sum of known expense line items = 51.56. Actual total = 58.86. Gap = 7.30. The missing items (interest 2.22 + subsidies 0.23 + court 0 + food bought 10.47 = 12.92) actually *overshoot* the gap — suggesting some overlap between food bought and other categories, or that food is netted out differently. The total `economy.expense` should be treated as the authoritative figure.

#### Balance & Debt

| # | Field | JSON Path | Raw (FRA) | Keep? | Status | Notes |
|---|-------|-----------|-----------|-------|--------|-------|
| 48 | Monthly balance | `economy.income - economy.expense` | `21.94` | derived | **OK** | Matches `recent_balance[-1]` exactly. Not a stored field — derived from income and expense. |
| 49 | Gold monthly delta | `balance_history_2.Gold` | `9.65` | **YES** | **OK** | Monthly change in gold *stock* (treasury). Different from income-expense balance because it includes one-off events (lump sums, war reparations, etc.) that don't flow through income/expense. Represents the actual treasury change. |
| 50 | Total debt | `economy.total_debt` | `362.72` | **YES** | **OK** | Outstanding loan total. |
| 51 | Loan capacity | `economy.loan_capacity` | `2985.10` | **YES** | **OK** | Maximum borrowing capacity. |

#### Maintenance Sliders (`economy.maintenances`)

Sliders are multipliers (0.0–1.0) controlling spending on each category. Player-controlled. Useful for fixed vs variable cost analysis.

| # | Slider | JSON Path | Raw (FRA) | Keep? | Status | Notes |
|---|--------|-----------|-----------|-------|--------|-------|
| 52 | Army | `economy.maintenances.ArmyMaintenance` | `1.0` | **YES** | **OK** | 100% maintenance |
| 53 | Naval | `economy.maintenances.NavyMaintenance` | `1.0` | **YES** | **OK** | |
| 54 | Fort | `economy.maintenances.FortMaintenance` | `1.0` | **YES** | **OK** | |
| 55 | Cultural | `economy.maintenances.CulturalMaintenance` | `0.25` | **YES** | **OK** | |
| 56 | Colonial | `economy.maintenances.ColonialMaintenance` | `0.5` | **YES** | **OK** | |
| 57 | Exploration | `economy.maintenances.ExplorationMaintenance` | `0.5` | **YES** | **OK** | |
| 58 | Court | `economy.maintenances.CourtMaintenance` | — (not set for FRA) | **YES** | **NOT TRACKED** | Found on 2105 countries in this save. FRA doesn't have it set — likely defaults to some value. Must add to catalog. |
| 59 | Food | `economy.maintenances.FoodMaintenance` | `1.0` | **YES** | **NOT TRACKED** | Controls food purchasing. Must add to catalog. |
| 60 | Upkeep | `economy.maintenances.UpkeepMaintenance` | `1.0` | **YES** | **NOT TRACKED** | General upkeep slider. Must add to catalog. |
| 61 | Diplomatic | `economy.maintenances.DiplomaticMaintenance` | — (not set for FRA) | **YES** | **NOT TRACKED** | Found on other countries. Must add to catalog. |

#### Tax Rates (`economy.tax_rates`)

Per-estate tax rate settings. Player-controlled.

| # | Estate | JSON Path | Raw (FRA) | Keep? | Status | Notes |
|---|--------|-----------|-----------|-------|--------|-------|
| 62 | Nobles | `economy.tax_rates.nobles_estate` | `0.126` (12.6%) | **YES** | **OK** | |
| 63 | Burghers | `economy.tax_rates.burghers_estate` | `0.439` (43.9%) | **YES** | **OK** | |
| 64 | Peasants | `economy.tax_rates.peasants_estate` | `0.476` (47.6%) | **YES** | **OK** | |

#### Historical Data

| # | Field | JSON Path | Shape | Keep? | Status | Notes |
|---|-------|-----------|-------|-------|--------|-------|
| 65 | Income history | `economy.monthly_gold` | 12-element array | **YES** | **OK** | 12 months of income values. Already tracked in field catalog. |
| 66 | Balance history | `economy.recent_balance` | 12-element array | **YES** | **OK** | 12 months of income−expense balance. Already tracked. |
| 67 | Historical tax base | `historical_tax_base` | 9 data points | **YES** | **NOT TRACKED** | Long-term tax base trend. Should add to catalog. |
| 68 | Historical population | `historical_population` | 9 data points | **YES** | **NOT TRACKED** | Long-term population trend. Should add to catalog. |
| 69 | Production | `last_month_produced` | dict (48 goods) | **YES** | **NOT TRACKED** | Goods production quantities. Interesting for trade/production analysis. Needs goods name localisation. |

#### Cumulative P&L

**No cumulative income/expense totals found anywhere in the save.** The game only stores current-month values and a 12-month rolling history. Cumulative P&L would need to be reconstructed by summing snapshots over time — this is a natural fit for our snapshot-based approach.

#### Economy Income & Expenses — Backlog

14. **[NEW] Navy maintenance**: Add `last_months_navy_maintenance` to field catalog. Key: `navy_maintenance`, category: `economy`.

15. **[NEW] Missing income/expense line items**: The following game UI fields have NO corresponding field in the extracted JSON: food sold (income), food bought (expense), interest on loans (expense), building subsidies (expense), court cost (expense). These are likely calculated at runtime by the game engine. **Options**: (a) accept that we can only track total income/expense and the line items we do have, (b) attempt to reconstruct: interest can be estimated from `loan_manager` objects × interest rate, food might be derivable from province/market data. For now: document as known gaps and rely on total income/expense as the authoritative figures.

16. **[NEW] Court maintenance slider**: Add `CourtMaintenance` to field catalog (under maintenance sliders). Also add `FoodMaintenance`, `UpkeepMaintenance`, `DiplomaticMaintenance`.

17. **[NEW] Historical tax base & population**: Add `historical_tax_base` and `historical_population` to field catalog. These provide long-term trend data beyond the 12-month rolling window.

18. **[NEW] Goods production**: Add `last_month_produced` to field catalog. Dictionary of goods → quantities. Needs goods key → display name localisation.

19. **[FEATURE] Cumulative P&L**: No cumulative data in save — must be reconstructed from snapshots. Since we store periodic snapshots with `economy.income` and `economy.expense`, we can sum these over time to build a cumulative P&L chart. Implementation: sum income/expense from all snapshots for a given country to approximate total income/expense since first snapshot.

20. **[FEATURE] Fixed vs variable cost analysis**: Maintenance sliders (0.0–1.0) represent the player's spending decisions. Costs that scale with slider position are "variable" (army, navy, fort, food). Costs independent of sliders are "fixed" (interest, possibly subsidies). This analysis can be done in frontend by correlating slider values with expense line items across snapshots.

---

## Open Questions

- [ ] Resolve `capital` location ID → location name key (needs game setup files — `common/locations/` or map definitions — to map numeric IDs to string keys like `"paris"`)
- [x] ~~Confirm meaning of `stability` scale~~ → Confirmed: −100 to +100. Three auto-modifiers in `common/auto_modifiers/country.txt`.
- [ ] Confirm `karma` / `purity` / `righteousness` — which religion mechanics use which? (needs `common/religions/` or `common/defines/`). For now: tracked for all countries, displayed only when relevant to current religion.
- [ ] Determine which cultures count as "discriminated" — need to cross-reference country pops with culture lists
- [ ] Manpower/sailors ×1000 and inflation ×100: decide whether to transform at storage or display time
- [ ] Missing economy line items (food sold/bought, interest, subsidies, court): can any be reconstructed from `loan_manager`, `market_manager`, or province data? Or accept as runtime-calculated?
- [ ] `balance_history_2.Gold` vs `economy.recent_balance[-1]`: confirmed different (9.65 vs 21.94). Gold delta = actual treasury change (including one-offs), recent_balance = income−expense only. Verify this interpretation with more data points.
- [ ] `CourtMaintenance` absent for FRA — what is the default value? Check other countries or game defaults.
- [ ] `historical_tax_base` and `historical_population` — what are the 9 data points? Time intervals? Need to check structure (array of values? array of {date, value}?).
