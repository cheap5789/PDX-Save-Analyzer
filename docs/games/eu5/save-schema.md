# EU5 Save File — Format Documentation

> All findings in this document are empirically derived from analyzing an actual EU5 autosave file.
> Game version: **1.1.10**
> Nothing here is assumed — only observed.

---

## Table of Contents

- [File Identification](#file-identification)
- [Overall File Structure](#overall-file-structure)
  - [Section 1 — Pre-ZIP Header (~395 KB)](#section-1--pre-zip-header-395-kb)
  - [Section 2 — ZIP Archive](#section-2--zip-archive)
- [Jomini Binary Token Format](#jomini-binary-token-format)
- [Parsing Chain](#parsing-chain)
- [Observed Metadata (from sample autosave)](#observed-metadata-from-sample-autosave)
- [Top-Level JSON Structure](#top-level-json-structure-empirically-discovered)
- [`metadata` Object](#metadata-object)
- [`played_country` Object](#played_country-object)
- [`countries` Object](#countries-object)
  - [Country Object — Key Fields](#country-object--key-fields)
- [`provinces` Object](#provinces-object)
  - [Province Object — Key Fields](#province-object--key-fields-sample)
- [`character_db` Object](#character_db-object)
  - [Character Object — Key Fields](#character-object--key-fields)
- [`situation_manager` Object](#situation_manager-object)
- [Resolved Questions](#resolved-questions)
- [Data Quality Audit — Field-by-Field](#data-quality-audit--field-by-field)
  - [Identity & Metadata](#identity--metadata)
  - [Economy — currency_data (resource pools)](#economy--currency_data-resource-pools)
  - [Economy — Income & Expenses](#economy--income--expenses)
  - [Technologies — Advances & Counters](#technologies--advances--counters)
  - [Military](#military)
  - [Score](#score)
  - [Government](#government)
  - [Religion & Diplomacy](#religion--diplomacy)
- [Open Questions](#open-questions)

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
│  SECTION 2: ZIP Archive         │  ~34.5 MB compressed
│  ├── gamestate                  │  136.4 MB uncompressed (~32.7 MB compressed, 76% ratio)
│  └── string_lookup              │    3.4 MB uncompressed  (~1.76 MB compressed, 50% ratio)
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
- **Compressed size:** ~32.7 MB (76% compression ratio)
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
Parsing time for a 34.5 MB save file (136.4 MB uncompressed gamestate): fast (< 2s).

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

| Key | Type | Sample value | Notes |
|-----|------|-------------|-------|
| `name` | string | `"Capitaine Erin"` | Player's character/ruler name |
| `id` | int | `4` | Player slot ID |
| `country` | int | `2186` | Numeric ID into `countries.database` |
| `player_proficiency` | string | `"EXPERT"` | |
| `same_name` | bool | `true` | |

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
| `stability` | 23.09 | Stability (scale: −100 to +100) |
| `inflation` | 0.00023 | Inflation |
| `prestige` | 75.70 | Prestige |
| `army_tradition` | 41.24 | Army tradition |
| `government_power` | 80.36 | Government power |
| `karma` | -58.67 | Religion-specific currency. Used by: `bon`, `mahayana`, `theravada`, `sammitiya`, `tibetan_buddhism`. Present in save for all countries; only shown in UI when relevant to current religion. |
| `religious_influence` | 49.18 | Religious influence |
| `purity` | 60 | Religion-specific currency. Used by: `shinto`. Present in save for all countries; only shown in UI when relevant to current religion. |
| `righteousness` | 90 | Religion-specific currency. Used by: `sanjiao`. Present in save for all countries; only shown in UI when relevant to current religion. |

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
> Reference save: Greenland playthrough (`saves/autosave.eu5`), autosave at **1345.10.1**, game version 1.1.10.
> Player: Greenland (tag `GRL`, country ID `13`). Multiplayer game.
> Reference country: France (tag `FRA`, country ID `1135`) — a great power with all field types populated.
> Country ID lookup method: `countries.tags` is a top-level dict `{numeric_id_string: "TAG"}`. FRA found at ID `"1135"`. Confirmed via `countries.database["1135"].country_name == "FRA"`.

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
| 26 | Karma | `currency_data.karma` | `-40.80` | — (not shown for Catholics) | Religion-specific currency. Present in save even if not used by current religion. | None | `karma` | **OK** | Used by: `bon`, `mahayana`, `theravada`, `sammitiya`, `tibetan_buddhism`. Not shown for other religions. Tracked for all — relevant on conversion. |
| 27 | Religious Influence | `currency_data.religious_influence` | `39.14` | 39.14 | Direct value. | None | `religious_influence` | **OK** | |
| 28 | Purity | `currency_data.purity` | `60` | — (not shown for Catholics) | Religion-specific. Present in save even if not used by current religion. | None | `purity` | **OK** | Used by: `shinto`. Not shown for other religions. Tracked for all — relevant on conversion. |
| 29 | Righteousness | `currency_data.righteousness` | `90` | — (not shown for Catholics) | Religion-specific. Same as above. | None | `righteousness` | **OK** | Used by: `sanjiao`. Not shown for other religions. Tracked for all — relevant on conversion. |
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

### Technologies — Advances & Counters

#### Advances (`researched_advances` + `counters.Advances`)

`researched_advances` is a dict of `{advance_key: true}` — all values are always `true` since advances cannot be un-researched. It is effectively a **set** of researched advance string keys.

`counters.Advances` = total advances researched **including the one currently being researched** (i.e. always `len(researched_advances) + 1` while a research is in progress). This is the number displayed in the game UI.

| # | Field | JSON Path | Raw (FRA, 1345) | Game UI | Store | Status | Notes |
|---|-------|-----------|-----------------|---------|-------|--------|-------|
| 70 | Advance count | `counters.Advances` | `71` | 70 (researched) + 1 (in progress) | **YES** | **NOT TRACKED** | The authoritative advance count. Includes the currently-researching advance. Store this integer — it tells you tech level at a glance. |
| 71 | Researched advance set | `researched_advances` | 70 keys (dict) | — | **YES (set of keys)** | **NOT TRACKED** | Store the full set of advance keys per snapshot. Enables detecting newly researched advances between snapshots (diff between consecutive snapshots). Cross-referencing with game files for effects is a later-stage task. |

**Sample advance keys at 1345 (FRA)** — mix of categories visible in the key names:

| Category | Example keys |
|----------|-------------|
| Core/general | `scholasticism`, `mapmaking`, `guilds`, `feudalism_advance`, `road_building` |
| Military | `castle_advance`, `fort_limit_1_advance`, `faster_levy_recruitment` |
| Unit unlocks | `unlock_footmen_advance`, `unlock_archers_advance`, `unlock_cog_advance` |
| Economy | `banking_advance` *(not yet at 1345)*, `taxation_advance`, `mining_advance` |
| Culture/law | `salic_law_advance`, `cultural_traditions_law_advance`, `partition_inheritance_advance` |
| National (French) | `french_heritage`, `french_tradition` |

Note: `researched_advances` contains all advance types in one flat dict — core advances, unit unlocks, laws, national traditions, etc. The game UI's tech count matches `counters.Advances - 1` (excluding the in-progress one).

#### Country Counters (`counters`)

All are cumulative lifetime integers. Never decrease (except `LivingCharacters`).

| # | Counter key | FRA (1345) | GRL (1345) | Meaning | Track? |
|---|-------------|------------|------------|---------|--------|
| 72 | `Advances` | 71 | 68 | Advances researched incl. in-progress | **YES** — see above |
| 73 | `BorderLocations` | 34 | 3 | Locations on country's border | **YES** |
| 74 | `BuildingLevelChanged` | 25 | 2 | Cumulative building level changes | **YES** |
| 75 | `CabinetCardModifier` | 22 | 12 | Cabinet card interactions | **YES** |
| 76 | `CoastalLocations` | 17 | 3 | Coastal locations owned | **YES** |
| 77 | `ConstructionStarted` | 48 | 2 | Constructions ever started | **YES** |
| 78 | `Diplomacy` | 382 | 7 | Diplomatic actions taken | **YES** |
| 79 | `DiscoveredLocations` | 3 | 3 | Locations explored/discovered | **YES** |
| 80 | `Locations` | 195 | 13 | Total locations owned | **YES** |
| 81 | `RGO` | 70 | — | RGO level count | **YES** |
| 82 | `Reforms` | 2 | 2 | Government reforms enacted | **YES** |
| 83 | `Siege` | 5 | — | Total sieges | **YES** |
| 84 | `Wars` | 74 | — | Wars participated in | **YES** |
| 85 | `WorksOfArt` | 3 | — | Works of art created | **YES** — not present in GRL at 1345 (likely 0/absent) |
| — | `Anything` | 1,348 | 243 | Total events fired — meaning unclear | **NO** — document as investigation topic |
| — | `LivingCharacters` | 228 | 23 | Living characters associated | **NO** — not a useful country-level stat |
| — | `Pops` | 111 | 109 | Count of pop *objects* (not population size) | **NO** — misleading: actual population = sum of `size` across all pops in country's locations |
| — | `PrimaryCulture` | 2 | 2 | Every country has 2 here — meaning unclear | **NO** — skip |
| — | `Rebels` | 26 | 4 | Rebel movements ever created | **NO** |
| — | `SubjectTree` | 48 | 2 | Unknown — skip | **NO** |
| — | `TradePath` | 3 | 3 | Trade paths | **NO** |

> **Note on `Pops` counter**: The `population.database` has 115,951 pop objects globally, each carrying a `size` field (e.g. pop #0 has size 0.224). Locations list their pops; locations are assigned to owner countries. True population = sum of `size` across all pops in all locations owned by the country. The `counters.Pops` integer is a count of pop *objects* (not their total size) and is not a useful population figure.

> **Note on `Anything` counter**: Suspected to be a total fired-event count. Varies widely (FRA 1348 vs GRL 243 — GRL is a minor power with little history). To investigate: check `event_manager` structure and whether event records have a per-country count matching this value.

#### Current Research (`current_research`)

France is researching 4 advances simultaneously in its queue:

| Field | Value | Notes |
|-------|-------|-------|
| `current_research.research` | `[1071, 591, 552, 551]` | Research queue — **last item is actively being researched**, rest are waiting |
| `current_research.progress` | `6.04` | Progress toward completing the active advance. Threshold unknown — needs game data. |
| Active advance | `improve_relation_impact_renaissance` (ID 551) | Resolved via `advance_manager.database[551].t` |
| Queued (waiting) | `devotio_moderna`, `renaissance_subject_opinions_advance`, `late_feudal_relations` | Will be researched in reverse order once active completes |

**`advance_manager.database`** (top-level in save): Global mapping of integer ID → advance key string (`{id: {t: "advance_key"}}`). 2,629 total advances in the game. Essential lookup table for resolving `current_research` IDs. IDs are stable across saves (same advance always has the same integer ID).

#### Advances & Counters — Backlog

21. **[NEW] Advance count tracking**: Add `counters.Advances` to field catalog. Key: `advances`, category: `technology`, display: "Advances". Store as integer. This is the primary tech level indicator.

22. **[NEW] Researched advance set**: Store `researched_advances` dict keys as a list per snapshot. Enables advance-diff between snapshots (detect newly researched advances). Category: `technology`. At this stage: store only, no per-advance effect lookup.

23. **[NEW] Current research tracking**: Store `current_research.research[-1]` (the active advance key, resolved via `advance_manager`) and `current_research.progress` per snapshot. Also store the full queue (`research[:-1]`) for context. Key: `current_research_advance`, `current_research_progress`.

24. **[NEW] Advance classification**: Parse `common/advances/` game files to classify each advance by research domain (scientific, social, military, economic, etc.). One-shot task at startup (or once per game version). Result stored as a lookup table used to enrich `researched_advances` display. **Not a priority now** — document as future enhancement.

25. **[NEW] Country counters**: Add the following counters to the field catalog (all from `counters.*`): `BorderLocations`, `BuildingLevelChanged`, `CabinetCardModifier`, `CoastalLocations`, `ConstructionStarted`, `Diplomacy`, `DiscoveredLocations`, `Locations`, `RGO`, `Reforms`, `Siege`, `Wars`, `WorksOfArt`. Category: `counters`. These are cumulative lifetime stats — interesting for historical trend analysis and event detection (e.g. spike in Wars counter = war started).

26. **[INVESTIGATE] `Anything` counter**: Suspected total fired-event count. Needs cross-referencing with `event_manager` database to confirm. Document as future investigation.

---

#### Economy Income & Expenses — Backlog

14. **[NEW] Navy maintenance**: Add `last_months_navy_maintenance` to field catalog. Key: `navy_maintenance`, category: `economy`.

15. **[NEW] Missing income/expense line items**: The following game UI fields have NO corresponding field in the extracted JSON: food sold (income), food bought (expense), interest on loans (expense), building subsidies (expense), court cost (expense). These are likely calculated at runtime by the game engine. **Options**: (a) accept that we can only track total income/expense and the line items we do have, (b) attempt to reconstruct: interest can be estimated from `loan_manager` objects × interest rate, food might be derivable from province/market data. For now: document as known gaps and rely on total income/expense as the authoritative figures.

16. **[NEW] Court maintenance slider**: Add `CourtMaintenance` to field catalog (under maintenance sliders). Also add `FoodMaintenance`, `UpkeepMaintenance`, `DiplomaticMaintenance`.

17. **[NEW] Historical tax base & population**: Add `historical_tax_base` and `historical_population` to field catalog. These provide long-term trend data beyond the 12-month rolling window.

18. **[NEW] Goods production**: Add `last_month_produced` to field catalog. Dictionary of goods → quantities. Needs goods key → display name localisation.

19. **[FEATURE] Cumulative P&L**: No cumulative data in save — must be reconstructed from snapshots. Since we store periodic snapshots with `economy.income` and `economy.expense`, we can sum these over time to build a cumulative P&L chart. Implementation: sum income/expense from all snapshots for a given country to approximate total income/expense since first snapshot.

20. **[FEATURE] Fixed vs variable cost analysis**: Maintenance sliders (0.0–1.0) represent the player's spending decisions. Costs that scale with slider position are "variable" (army, navy, fort, food). Costs independent of sliders are "fixed" (interest, possibly subsidies). This analysis can be done in frontend by correlating slider values with expense line items across snapshots.

### Military

#### Force Sizes

| # | Field | JSON Path | Raw (FRA) | Scale / Notes | Keep? | Status |
|---|-------|-----------|-----------|---------------|-------|--------|
| 86 | Army size | `expected_army_size` | `23.21` | Indicative. No direct gameplay effect currently. FRA=23.2, ENG=10.7, CAS=21.4, GRL≈0 | **YES** | **NOT TRACKED** |
| 87 | Navy size | `expected_navy_size` | `40` | Indicative. No direct gameplay effect currently. FRA=40, ENG=55, CAS=36, GRL=0 | **YES** | **NOT TRACKED** |
| 88 | Max manpower | `max_manpower` | `0.9108` | ×1000 → 910.8 (already backlogged #8) | **YES** | **NEEDS FIX** |
| 89 | Max sailors | `max_sailors` | `0.1242` | ×1000 → 124.2 (already backlogged #9) | **YES** | **NEEDS FIX** |
| 90 | Manpower/month | `monthly_manpower` | `0.00412` | ×1000 → 4.12/month regeneration rate | **YES** | **NOT TRACKED** |
| 91 | Sailors/month | `monthly_sailors` | `0.00138` | ×1000 → 1.38/month regeneration rate | **YES** | **NOT TRACKED** |
| 92 | Manpower losses | `this_months_manpower_losses` | `-0.13108` | ×1000 → -131.1 this month (combat + attrition) | **YES** | **NOT TRACKED** |
| 93 | Naval range | `naval_range` | `1000` | Same for all countries at 1345 — evolves differently per country as tech advances | **YES** | **NOT TRACKED** |
| 94 | Colonial range | `colonial_range` | `1000` | Same situation as naval range | **YES** | **NOT TRACKED** |

#### Subunits (`owned_subunits` → `subunit_manager.database`)

FRA has 145 subunits at 1345. These are individual regiments (army) and ships (navy), each stored as an object in `subunit_manager.database`.

**Key fields per subunit:**

| Field | Sample | Notes |
|-------|--------|-------|
| `type` | `a_feudal_levy`, `a_mailed_knights`, `a_footmen`, `n_cog` | Unit type key. Prefix `a_` = army unit, `n_` = naval unit. Resolves to game data via `common/unit_types/`. |
| `strength` | `0.5` | Current strength as fraction of max (0–1). Max strength varies by unit type and age — requires `common/unit_types/` to convert to actual troop count. |
| `morale` | `3.63` | Current morale (absolute value, scale defined per unit type in game data). |
| `experience` | `1.57` | Combat experience accumulated. |
| `home` | `2179` (location ID) | Recruitment home location. |
| `culture` / `religion` | int IDs | Culture and religion of the regiment. |
| `unit` | int ID | ID of the army group (in `unit_manager.database`) this subunit belongs to. |
| `attrition_losses_per_month` | `[-1,-1,...,0.025,...]` | 12-element array (one per month). -1 = no attrition that month. Active values = fraction lost. |
| `missing` | `{demand: "...", weaponry: 0, ...}` | Supply demands not met. Indicates maintenance type required and resource shortfalls. |

**FRA composition at 1345:**

| Type | Count | Notes |
|------|-------|-------|
| `a_feudal_levy` | 109 | Standard medieval infantry |
| `a_mailed_knights` | 27 | Heavy cavalry |
| `a_footmen_levy` | 7 | Footmen |
| `a_footmen` | 1 | Professional footmen |
| `n_cog` | 1 | Cog (merchant ship used as warship) |

**Deployed manpower estimation**: Cannot be done with a simple heuristic. `strength` (0–1) × unit max strength (from `common/unit_types/`) = actual troop count per regiment. Each unit type has its own max strength defined in `game/in_game/common/unit_types/` (e.g. `a_age_2_renaissance_infantry` has max strength 1.000). **Cross-referencing game unit type files is required for accurate headcount.** This is a future enhancement.

#### Army Groups (`units` → `unit_manager.database`)

FRA has 9 army groups. Each group object contains: name, `is_army` flag, formation preference, food supply state, `frontage` (max regiment width), `leader` (character ID), current `location` (location ID), and battle result history.

These are not snapshot-level fields — army group composition changes constantly during play. **Not tracked per snapshot.** Army count (= `len(units)`) could be derived but has limited analytical value.

#### Military — Backlog

27. **[NEW] Force sizes**: Add `expected_army_size` and `expected_navy_size` to field catalog. Indicative-only values currently, but useful for tracking military buildup trends. Category: `military`.

28. **[NEW] Monthly manpower/sailors**: Add `monthly_manpower` and `monthly_sailors` to field catalog (×1000 transform). Add `this_months_manpower_losses` (×1000 transform, negative value = losses). Category: `military`.

29. **[NEW] Naval and colonial range**: Add `naval_range` and `colonial_range` to field catalog. Category: `military`. Values are the same for all countries at game start but diverge over time as countries research different advances — tracking over time shows which countries are investing in overseas projection.

30. **[FUTURE] Subunit deployed manpower**: Accurate troop count requires `strength` × unit-type-specific max strength from `common/unit_types/`. Implementation: parse unit type files at startup to build a `{unit_type_key: max_strength}` lookup. Then for each subunit: `actual_troops = subunit.strength × lookup[subunit.type]`. Sum across all subunits for total army size. This would replace the approximate `expected_army_size`.

31. **[FUTURE] Army composition breakdown**: Once unit types are parsed, group subunits by type category (infantry/cavalry/artillery/naval) per snapshot. Enables tracking how a country's military composition evolves (e.g. transition from feudal levies to professional armies).

### Score

#### Age System

Age transitions are **universal** — same date for every country simultaneously:

| Age # | Name | Start date | Notes |
|-------|------|-----------|-------|
| 1 | Age of Traditions | Game start | |
| 2 | Renaissance | 1342 | |
| 3 | Age of Discovery | 1437 | |
| 4 | Age of Reformation | 1537 | |
| 5 | Age of Absolutism | 1637 | Pattern: 1x37 from age 3 onward |
| 6 | Age of Revolutions | 1737 | |

Score is **cumulative within an age and resets to 0 at each age transition**. Only countries ranked **top 10** in a category (ADM, DIP, MIL) earn score each month, scaled by rank. `age_score` is a 6-element array — non-zero only for completed or current ages. Absent entirely for countries that have never earned score.

#### Score Fields

| # | Field | JSON Path | FRA (1345) | GRL (1345) | ENG (1345) | Keep? | Status | Notes |
|---|-------|-----------|------------|------------|------------|-------|--------|-------|
| 95 | Overall rank | `score.score_place` | 4 | 67 | 9 | **YES** | **NOT TRACKED** | Leaderboard position across all countries. |
| 96 | ADM score | `score.score_rating.ADM` | 8.93 | 2.61 | 3.41 | **YES** | **NOT TRACKED** | Cumulative admin score for the current age. |
| 97 | DIP score | `score.score_rating.DIP` | 4.74 | 0.02 | 0.38 | **YES** | **NOT TRACKED** | |
| 98 | MIL score | `score.score_rating.MIL` | 4.97 | 0.32 | 0.83 | **YES** | **NOT TRACKED** | |
| 99 | ADM rank | `score.score_rank.ADM` | 6 | 828 | 68 | **YES** | **NOT TRACKED** | Rank among all countries. Only top 10 earn score per month. |
| 100 | DIP rank | `score.score_rank.DIP` | 5 | 334 | 30 | **YES** | **NOT TRACKED** | |
| 101 | MIL rank | `score.score_rank.MIL` | 3 | 867 | 16 | **YES** | **NOT TRACKED** | |
| 102 | Age scores | `score.age_score` | `[57.9, 48.6, 0, 0, 0, 0]` | absent | `[48.9, 18.5, 0, 0, 0, 0]` | **YES** | **NOT TRACKED** | 6-element array. Absent for countries with no score history — default to `[0,0,0,0,0,0]`. Resets at each age transition. |

#### Score — Backlog

35. **[NEW] Score tracking**: Add `score.score_place`, `score.score_rating.ADM/DIP/MIL`, `score.score_rank.ADM/DIP/MIL`, and `score.age_score` to field catalog. Category: `score`. Note: `age_score` may be absent — default to zeros. Age resets at universal dates (1342, 1437, 1537, 1637, 1737) must be accounted for in trend visualizations.

---

### Government

#### Country Rank & Level

Country rank progresses as a country grows: **county (1) → duchy (2) → kingdom (3) → empire (4)**. Stored as integer `level` on the country object. Absent = 1 (county). `country_rank_history` records progression as a list of rank milestone strings — useful for event detection.

| # | Field | JSON Path | FRA | GRL | Keep? | Status | Notes |
|---|-------|-----------|-----|-----|-------|--------|-------|
| 103 | Country level | `level` | `3` (kingdom) | absent (=1, county) | **YES** | **NOT TRACKED** | Integer 1–4. Absent = county = 1. Rank-up = governance event. |
| 104 | Rank history | `country_rank_history` | `[rank_county, rank_kingdom]` | — | **YES** | **NOT TRACKED** | List of rank milestone strings. Diff between snapshots → rank-up event ("France became a Kingdom"). |
| 105 | Government type | `government.type` | `monarchy` | — | **YES** | **NOT TRACKED** | Localise. Merges identity backlog #4 and earlier #33. Changes are governance events. |
| 106 | Succession law | `government.heir_selection` | `salic_law` | — | **YES** | **NOT TRACKED** | Localise → "Salic Law". Changes are governance events. |
| 107 | Parliament type | `government.parliament.parliament_type` | `estate_parliament` | — | **YES** | **NOT TRACKED** | Infrequent but significant — transitions surface as governance milestone events. |

#### Ruler & Heir

Ruler/heir stats are on a **0–100 scale**. Ruler stats are integers. Heir stats are multiples of 0.25, accumulating gradually during childhood: 25% chance per month of +0.5 in one trait, weighted by education type. Both resolved from `character_db.database` via `government.ruler` and `government.heir` character IDs.

| # | Field | JSON Path | FRA ruler (John, ID=690) | FRA heir (Louis, ID=24617) | Keep? | Status | Notes |
|---|-------|-----------|--------------------------|---------------------------|-------|--------|-------|
| 108 | Ruler ADM | `character_db[government.ruler].adm` | 60 | 25 | **YES** | **NOT TRACKED** | 0–100 integer for rulers; 0.25 multiples for heirs. |
| 109 | Ruler DIP | `character_db[government.ruler].dip` | 62 | 12.5 | **YES** | **NOT TRACKED** | |
| 110 | Ruler MIL | `character_db[government.ruler].mil` | 57 | 16.25 | **YES** | **NOT TRACKED** | |
| 111 | Ruler name | `character_db[government.ruler].first_name` | `name_john` | `name_louis` | **YES** | **NOT TRACKED** | Localisation key → "John", "Louis". |
| 112 | Ruler birth | `character_db[government.ruler].birth_date` | `1319.4.26` | `1339.4.1` | **YES** | **NOT TRACKED** | Derive age at snapshot. Heir coming of age = governance event. |

> **Ruler change detection**: Track `government.ruler` ID per snapshot. Change between snapshots → "new ruler" event. Similarly `government.heir` change → "heir changed" event (death, disinheritance, new birth).

#### Societal Values (`government.societal_values`)

Sixteen political/ideological sliders evolving through events, reforms, and decisions. **Track over time** — they form a long-term political portrait of each country. Scale −100 to +100. **−999 = not applicable for this country** (e.g. `sinicized_vs_unsinicized` for European nations — filter before display).

| # | Slider key | FRA (1345) | Meaning | Keep? |
|---|-----------|------------|---------|-------|
| 113 | `centralization_vs_decentralization` | 95 | Very centralized | **YES** |
| 114 | `aristocracy_vs_plutocracy` | -85 | Very aristocratic | **YES** |
| 115 | `serfdom_vs_free_subjects` | -80 | Heavily serf-based | **YES** |
| 116 | `offensive_vs_defensive` | -40 | Slightly defensive | **YES** |
| 117 | `land_vs_naval` | -46 | Land power focus | **YES** |
| 118 | `quality_vs_quantity` | -30 | Quantity-leaning | **YES** |
| 119 | `belligerent_vs_conciliatory` | -19 | Slightly belligerent | **YES** |
| 120 | `traditionalist_vs_innovative` | -30 | Traditional | **YES** |
| 121 | `spiritualist_vs_humanist` | -50 | Spiritualist | **YES** |
| 122 | `capital_economy_vs_traditional_economy` | 75 | Capital economy | **YES** |
| 123 | `individualism_vs_communalism` | -13 | Slightly communal | **YES** |
| 124 | `mercantilism_vs_free_trade` | -999 | N/A for France | **YES** (store -999, filter on display) |
| 125 | `outward_vs_inward` | -999 | N/A | **YES** |
| 126 | `sinicized_vs_unsinicized` | -999 | N/A (East Asian mechanic) | **YES** |
| 127 | `absolutism_vs_liberalism` | -999 | N/A | **YES** |
| 128 | `mysticism_vs_jurisprudence` | -999 | N/A | **YES** |

> **Visualization**: Radar/spider chart per snapshot (filtering -999 values) shows country's political profile at a point in time. Trend lines per active slider over time show how the country evolves ideologically. Challenge: variable number of applicable sliders per country.

#### Cabinet (skipped)

Cabinet entries (`government.cabinet_entries` → `cabinet_manager.database`) hold active government actions with targets and responsible characters. Too granular for snapshot tracking. Expansion is detected via location ownership changes (tracked separately).

#### Government — Backlog

36. **[NEW] Country level & rank history**: Add `level` (integer, absent=1) and `country_rank_history` (list of rank key strings) to field catalog. Category: `government`. Detect rank-up between snapshots → surface as event ("France became a Kingdom").

37. **[NEW] Government type & succession law**: Add `government.type` and `government.heir_selection` to field catalog. Category: `government`. Merges identity backlog items #4 and #16. Changes are governance events.

38. **[NEW] Parliament type**: Add `government.parliament.parliament_type` to field catalog. Category: `government`. Changes are significant governance milestone events.

39. **[NEW] Ruler & heir tracking**: Add ruler and heir ADM/DIP/MIL, name key, and birth date to field catalog. Resolve from `character_db` via `government.ruler` and `government.heir`. Category: `government`. Ruler ID change = ruler change event; heir ID change = heir change event.

40. **[NEW] Societal values**: Add all 16 `government.societal_values` fields to field catalog. Category: `government`. Store raw values including -999. Frontend filters -999 per country before display. Visualization: radar chart + per-slider trend lines.

41. **[FUTURE] Implemented laws/reforms/privileges**: Diff `government.implemented_laws`, `implemented_reforms`, and `implemented_privileges` between snapshots to detect "law adopted", "reform enacted", "privilege granted" events. Requires diff logic similar to advance detection.

---

### Religion & Diplomacy

#### Architectural Decision — Religion as a Parallel Entity

Religion is not merely a country attribute: it is a **first-class tracked entity**. Each religion entry in `religion_manager.database` has its own state (reformation meters, tithes, saint power, timed modifiers) and its country members change over time. The UI must expose a dedicated **Religion view** alongside the Country view, with:

- A list of all religions and their current member countries
- Demographic stats aggregated across member countries (pops, territory)
- Religion-specific variables (reform desire, tithe rate, saint power…)
- A timeline of membership changes (countries converting in or out)

This requires **parser refactoring** (a second tracked-entity type beyond countries, with its own snapshot table) and **frontend refactoring** (a parallel navigation rail entry and component set).

The Papacy (`PAP`) is handled as a regular country. The Religion view links to PAP's country page; no special entity type is needed.

---

#### Global Religion Entity (`religion_manager.database[id]`)

Religions are stored globally in `religion_manager.database`, keyed by a numeric ID. 293 religions exist in the sample save. Each entry has a rich structure. Fields worth tracking per religion snapshot:

| # | Field | JSON Path | Catholic (ID=12) sample | Keep? | Status | Notes |
|---|-------|-----------|------------------------|-------|--------|-------|
| 129 | Religion definition key | `religion_manager.database[id].definition` | `"catholic"` | **YES** | **NOT TRACKED** | Stable string key — use as display label seed. |
| 130 | Religion group | `religion_manager.database[id].group` | `"christian"` | **YES** | **NOT TRACKED** | Groups: christian, islamic, buddhist, dharmic, folk, … |
| 131 | Has religious head | `religion_manager.database[id].has_religious_head` | `true` | **YES** | **NOT TRACKED** | Boolean. True = governed by a head-of-religion country (e.g. PAP for Catholic). |
| 132 | Important country (head) | `religion_manager.database[id].important_country` | `"PAP"` | **YES** | **NOT TRACKED** | 3-letter tag of the religious head country. Absent if `has_religious_head=false`. |
| 133 | Reform desire | `religion_manager.database[id].reform_desire` | `0.0366` | **YES** | **NOT TRACKED** | Global meter (0.0–1.0). Rises over time; reaching threshold triggers the Reformation. Track as trend — a spike is a major world event. |
| 134 | Tithe rate | `religion_manager.database[id].tithe` | `0.02` | **YES** | **NOT TRACKED** | Tax rate paid to religious head. Drives PAP income. |
| 135 | Saint power | `religion_manager.database[id].saint_power` | `3772` | **YES** | **NOT TRACKED** | Accumulated saint power pool. Religion-specific mechanic. |
| 136 | Timed modifiers | `religion_manager.database[id].timed_modifier` | list (varies) | **YES** | **NOT TRACKED** | Count and types of active timed modifiers on the religion. |

> **Religion membership**: The country's `primary_religion` (numeric ID) links it to a religion. At each snapshot, derive member lists by scanning all countries' `primary_religion`. Store as a join table `(snapshot_id, religion_id, country_id)`.

> **Religion-specific currency variables** (`has_karma`, `has_purity`, `has_righteousness`) live on the religion definition; the matching values (`karma`, `purity`, `righteousness`) live in the country's `currency_data`. They are already tracked as economy fields (backlog #8-13); display them in the Religion view filtered by which mechanic the religion activates.

---

#### Per-Country Religion Fields

| # | Field | JSON Path | FRA (1345) | GRL (1345) | Keep? | Status | Notes |
|---|-------|-----------|------------|------------|-------|--------|-------|
| 137 | Primary religion ID | `countries.database[id].primary_religion` | `12` (catholic) | `12` (catholic) | **YES** | **NOT TRACKED** | Foreign key into `religion_manager.database`. Already identified in Identity section (#12) but not yet stored as a tracked field. |
| 138 | Religious aspects | `countries.database[id].religious_aspects` | `{}` | `{}` | **LOW** | **NOT TRACKED** | Empty in early game (1345). Likely populated later by events/choices. Skip until populated examples are found. |
| 139 | Saints | `countries.database[id].saints` | `[675]` | `[]` | **LOW** | **NOT TRACKED** | List of character IDs canonized as saints. Very specific mechanic. Skip for now; revisit if saint events become interesting to surface. |
| 140 | Current religious focus | `countries.database[id].current_religious_focus` | absent | absent | **LOW** | **NOT TRACKED** | Action slot. Not populated in early game. Skip. |

> **Summary**: Only `primary_religion` is needed at the country level (already captured as field #12). The Religion view derives all membership data from it. No other per-country religion fields are high priority at this stage.

---

#### Diplomacy — Per-Country Summary Fields

All fields from `countries.database[country_id]` directly.

| # | Field | JSON Path | FRA (1345) | Keep? | Status | Notes |
|---|-------|-----------|------------|-------|--------|-------|
| 141 | Diplomats | `countries.database[id].diplomats` | `1.24` | **YES** | **NOT TRACKED** | Diplomatic action points — a currency. Range 0 to ~10–12 (cap scales with techs). Spend on diplomatic actions (alliances, claim fabrication, etc.). Track per snapshot alongside gold and manpower. |
| 142 | Rivals | `countries.database[id].rivals_2` | list | **YES** | **NOT TRACKED** | List of rival country IDs. Summary diplomatic posture. Track count + IDs. |
| 143 | Enemies | `countries.database[id].enemies` | list | **YES** | **NOT TRACKED** | List of enemy country IDs (declared enemies, distinct from war belligerents). Track count + IDs. |
| 144 | Last war date | `countries.database[id].last_war` | date string | **YES** | **NOT TRACKED** | Date the country last entered a war. Useful for peace/war cycle analysis. |
| 145 | Last peace date | `countries.database[id].last_peace` | date string | **YES** | **NOT TRACKED** | Date the country last made peace. Together with `last_war` defines recent belligerence. |

---

#### Wars (`war_manager.database`) — Architecture Decision

Wars are a **first-class tracked entity**, alongside countries and religions. 39 active dict-entries + 27 null slots were observed in the Greenland save at 1345. Concluded wars retain their full record in the save (`end_date` present, `previous=true`) — **keep forever** as permanent historical records.

> **Storage note**: `war_manager.database` contains null `"none"` sentinel entries (27 of 66 IDs in sample) — these are skipped during parsing.

---

#### War Identity & Static Fields

Populated once when a war is first detected; not re-written on subsequent snapshots unless `end_date` appears.

| Field | JSON path | Sample | Notes |
|-------|-----------|--------|-------|
| War ID | key in `war_manager.database` | `33554491` | Numeric string. Stable for the war's lifetime. |
| Name key | `war_name.name` | `NORMAL_WAR_NAME` | Localisation key. Observed: `NORMAL_WAR_NAME`, `CIVIL_WAR_NAME`, `INDEPENDENCE_WAR_NAME`, `AGRESSION_WAR_NAME`, `NANBOKUCHOU_WAR_NAME`. |
| Name bases | `war_name.bases` | `{First: {name: "..."}, Second: {name: "..."}}` | Two named anchors used to generate the human-readable war name (e.g. "War of the French Succession"). Store as JSON for localisation at display time. |
| Start date | `start_date` | `"1344.10.5"` | EU5 date string. |
| End date | `end_date` | `"1344.10.19"` (concluded) | Absent in ongoing wars. Presence = war over. |
| Civil war flag | `has_civil_war` | `true` / absent | Boolean. True = internal revolt type war. |
| Revolt flag | `revolt` | `true` / absent | Distinct from `has_civil_war`; 7 revolt wars observed (overlaps). |
| Original attacker | `original_attacker` | `1135` (FRA) | Country ID of the war initiator. |
| Original target | `original_attacker_target` | `1411` | Country ID of the primary defender. |
| Original defenders | `original_defenders` | `[1411]` | List of country IDs on defender side at war start (usually same as target). |
| Goal type | one of the goal keys | `"independence"` | Mutually exclusive key: `take_province`, `superiority`, `independence`, `dependency`, `destroy_army`, `opinion_improvement`, `revolt`, `scripted_oneway`, `potential_for_diplomacy`. |
| Casus belli | `<goal_key>.casus_belli` | `"cb_independence_war"` | String key. Observed: `cb_conquer_enemy`, `cb_independence_war`, `cb_deus_vult`, `cb_humiliate`, `cb_force_migration`, `cb_nanbokuchou`, `cb_parliament_conquer_province`, `cb_none`, etc. |
| Goal target | `<goal_key>.target` | `{target_province: 3697, target_locations: 15644}` | Varies by goal type. Province/country/subject type. Store as JSON blob. For `dependency`: `{first, second, subject_type}`. |

---

#### War Snapshot Fields

Per-snapshot state — stored at each save snapshot alongside country and religion snapshots.

| Field | JSON path | Sample | Notes |
|-------|-----------|--------|-------|
| Attacker score | `attacker_score` | `17` | Cumulative attacker war score pool. Not ±100 — grows independently from defender score. |
| Defender score | `defender_score` | `8` | Cumulative defender war score pool. |
| Net war score | derived | `9` | `attacker_score − defender_score`. Positive = attackers winning. Display metric. |
| War direction (quarter) | `war_direction_quarter` | `-85` | Score momentum over last quarter. Negative = defenders gaining ground. Key trend indicator. |
| War direction (year) | `war_direction_year` | `-14` | Score momentum over last year. Smoothed version of quarter delta. |
| War goal held | `war_goal_held` | `1309` (location ID) | Location currently held by the side that controls the war goal. Present only in applicable goal types. |
| Occupied locations | `locations` | `{loc_id: country_id, …}` | Full occupation map: which country controls each location in the war theatre. Up to 1,395 entries in large wars. **Store as JSON blob** per snapshot — too many rows for a normalized table. |

> **Occupation map rationale**: The locations dict changes each snapshot as territory is taken or recaptured. Storing it as a JSON blob preserves the full picture cheaply. At display time, cross-reference with location→country metadata to compute "% of country X's territory occupied" or "total locations held by each side".

---

#### War Participants

Each participant is an entry in `war.all[n]`. A single country can appear only once per war. Participant status can change (Active → Left). Store as a **participant table** updated when status changes.

| Field | JSON path | Sample | Notes |
|-------|-----------|--------|-------|
| Country ID | `all[n].country` | `1135` | Foreign key to countries. |
| Side | `all[n].history.request.side` | `"Attacker"` / `"Defender"` | Fixed at join time. |
| Join reason | `all[n].history.request.reason` | `"InternationalOrganization"` | How they entered: `Instigator` (started it), `Target` (primary victim), `Subject` (dragged in as subject/vassal — 463 occurrences, by far most common), `Overlord`, `InternationalOrganization` (called by ally via IO like Papacy), `Scripted`. |
| Join type | `all[n].history.request.join_type` | `"Always"` | `Always` (obligated), `AutoCall` (auto-joined), `CanCall` (callable but not yet). |
| Called by | `all[n].history.request.called_ally` | `212` (country ID) | Present when reason = `InternationalOrganization` or ally-call. The country that pulled this one in. |
| Join date | `all[n].history.joined.date` | `"1344.10.5"` | EU5 date string. |
| Contribution scores | `all[n].history.joined.score` | `{Combat: 328.93, Siege: 0.36, JoiningWar: 1}` | Cumulative war score contributions by type. `JoiningWar` = 1 always (joining bonus); `Combat` and `Siege` grow with participation. |
| Losses | `all[n].history.joined.losses.losses` | `{army_infantry: {Battle: 2672, Attrition: 3626}, army_cavalry: {Battle: 1124, …}}` | Full breakdown: unit type × loss cause. Unit types: `army_infantry`, `army_cavalry`, `army_auxiliary`, `navy_galley`, `navy_transport`. Loss causes: `Battle`, `Attrition`, `Capture`. Store as JSON blob. |
| Status | `all[n].status` | `"Active"` | `Active`, `Left`, `Declined`. Left = exited via separate peace or capitulation. |
| IO link | `all[n].history.request.international_organization` | `16777280` (IO ID) | Present when `reason=InternationalOrganization`. The IO that obligated participation (e.g. Papacy for Catholic countries). |

> **Declined participants** (4 observed) represent countries that were called but refused to join — worth recording as "declined to join war X" event since it reveals diplomatic tension.

---

#### War Name Types & Goal Type Distribution

Observed in 39 active wars (Greenland save, 1345):

| War name key | Count | Typical scenario |
|---|---|---|
| `NORMAL_WAR_NAME` | 27 | Standard wars |
| `CIVIL_WAR_NAME` | 5 | Internal revolt |
| `AGRESSION_WAR_NAME` | 3 | Aggressive expansion |
| `INDEPENDENCE_WAR_NAME` | 2 | Subject breaking free |
| `NANBOKUCHOU_WAR_NAME` | 2 | Japan-specific succession war |

| Goal type | Count | Meaning |
|---|---|---|
| `superiority` | 19 | Generic dominance war (humiliate / conquer) |
| `revolt` | 7 | Internal revolt |
| `independence` | 8 | Subject seeking independence |
| `potential_for_diplomacy` | 7 | Diplomatic pressure war |
| `dependency` | 6 | Force a subject relationship |
| `take_province` | 5 | Claim a specific province |
| `destroy_army` | 2 | Destroy target's army |
| `opinion_improvement` | 2 | Force improved opinion |
| `scripted_oneway` | 1 | Scripted/event war |

---

#### Battle Sub-Events (Opportunistic)

`war_manager.database[id].battle` holds **only the most recent battle** in the war — there is no battle history array. Fields: `location` (ID), `date`, `is_land` (boolean), `war_attacker_win` (boolean), `war_score` (score change from this battle), per-side `losses` (8-slot array), `total`, `who` (country, size, tradition, experience), `character` (commanding character ID).

**Tracking decision**: Since only the last battle is stored, full battle history cannot be reconstructed. However, if `battle.date` differs between two consecutive snapshots, a new battle occurred. Record it as a war sub-event: location, date, winner side, war_score delta, both commanding characters, and aggregated losses. This is opportunistic — battles happening between two snapshot moments will be missed, but battles caught will enrich the war record significantly.

---

#### Skipped — Bilateral Relations & Named Diplomatic Actions

Per-country bilateral `relations` sub-dicts (Opinion, Trust, Antagonism biases per pair) are **skipped** — too granular and voluminous at this maturity level. Named diplomatic actions in `diplomacy_manager` (alliances, dependencies, royal marriages, etc.) are also **skipped** for now. Both may be revisited at a high maturity level.

---

#### Religion, Diplomacy & Wars — Backlog

42. **[NEW] Religion entity table**: Create a `religions` tracked-entity type in the parser. Each snapshot records one row per religion in `religion_manager.database` containing: `definition`, `group`, `has_religious_head`, `important_country`, `reform_desire`, `tithe`, `saint_power`, `timed_modifier_count`. Category: `religion`.

43. **[NEW] Religion membership join table**: Each snapshot records `(snapshot_id, religion_id, country_id)` for every country's `primary_religion`. Replaces storing religion as a plain country field. Category: `religion`.

44. **[NEW] Parser refactor — religion as parallel tracked entity**: Extend the parser's snapshot loop to populate religion snapshot rows alongside country snapshot rows. Requires a second entity loop over `religion_manager.database`. Category: `architecture` / `parser`.

45. **[NEW] Frontend — Religion view**: Add a Religion navigation entry parallel to Countries. Religion list page: table of all religions with member count, reform desire, tithe, has_religious_head. Religion detail page: member country list, demographic aggregates, religion-specific variable trends (reform desire over time, saint power over time). Category: `frontend`.

46. **[NEW] Diplomats field**: Add `diplomats` (float, 0–~12) to the country snapshot field catalog. Category: `economy` (treat as a currency alongside gold/manpower/sailors). Store per snapshot.

47. **[NEW] Rivals & enemies tracking**: Add `rivals_2` (list of country IDs) and `enemies` (list of country IDs) to the country snapshot field catalog. Store count + serialized ID list. Category: `diplomacy`.

48. **[NEW] Last war / last peace dates**: Add `last_war` and `last_peace` date strings to the country snapshot field catalog. Category: `diplomacy`.

49. **[NEW] War entity table (static)**: Create a `wars` table populated once per war. Fields: war_id, name_key, name_bases (JSON), start_date, end_date (nullable), is_civil_war, is_revolt, original_attacker_id, original_attacker_target_id, original_defenders (JSON list), goal_type, casus_belli, goal_target (JSON). Category: `wars` / `architecture`.

50. **[NEW] War snapshot table**: Per snapshot, store: war_id, snapshot_id, attacker_score, defender_score, net_war_score (derived), war_direction_quarter, war_direction_year, war_goal_held (location ID, nullable), occupied_locations (JSON blob `{location_id: country_id}`). Category: `wars`.

51. **[NEW] War participant table**: Per (war_id, country_id): side, join_reason, join_type, called_by (country_id, nullable), join_date, io_id (nullable), status (Active/Left/Declined), score_combat, score_siege, score_joining, losses (JSON blob `{unit_type: {cause: count}}`). Update status field when participant exits. Category: `wars`.

52. **[NEW] Parser refactor — wars as parallel tracked entity**: Extend the snapshot loop to process `war_manager.database`. On each snapshot: (a) detect new wars → insert into `wars` table + insert all participants; (b) update `end_date` for newly concluded wars; (c) detect status changes in participants (Active → Left); (d) insert war snapshot row with scores and occupation map. Skip null `"none"` entries. Category: `architecture` / `parser`.

53. **[NEW] War events**: Derive events from war processing: "war started" (new war_id), "war ended" (end_date appeared), "country joined war" (new Active participant), "country left war" (status → Left), "country declined" (status = Declined). Emit with war_id, country_id, side, date context. Category: `events`.

54. **[NEW] Battle sub-events**: When processing a war snapshot, if `battle.date` differs from the previously stored value, record a battle event: war_id, location_id, date, is_land, winner_side, war_score_delta, attacker_country_id, attacker_character_id, defender_country_id, defender_character_id, attacker_losses (JSON), defender_losses (JSON). Category: `events` / `wars`.

55. **[NEW] Frontend — War view**: Add a War navigation entry. War list page: all wars (active first, then concluded) with name, start/end dates, participant count, current net score. War detail page: participants list with side/losses/contribution score, war score trend line over snapshots, occupation map evolution, battle events timeline. Category: `frontend`.

---

- [ ] Resolve `capital` location ID → location name key (needs game setup files — `common/locations/` or map definitions — to map numeric IDs to string keys like `"paris"`)
- [x] ~~Confirm meaning of `stability` scale~~ → Confirmed: −100 to +100. Three auto-modifiers in `common/auto_modifiers/country.txt`.
- [ ] Confirm `karma` / `purity` / `righteousness` — which religion mechanics use which? (needs `common/religions/` or `common/defines/`). For now: tracked for all countries; the Religion view filters them by `has_karma` / `has_purity` / `has_righteousness` flags on the religion definition.
- [ ] Determine which cultures count as "discriminated" — need to cross-reference country pops with culture lists
- [ ] Manpower/sailors ×1000 and inflation ×100: decide whether to transform at storage or display time
- [ ] Missing economy line items (food sold/bought, interest, subsidies, court): can any be reconstructed from `loan_manager`, `market_manager`, or province data? Or accept as runtime-calculated?
- [ ] `balance_history_2.Gold` vs `economy.recent_balance[-1]`: confirmed different (9.65 vs 21.94). Gold delta = actual treasury change (including one-offs), recent_balance = income−expense only. Verify this interpretation with more data points.
- [ ] `CourtMaintenance` absent for FRA — what is the default value? Check other countries or game defaults.
- [ ] `historical_tax_base` and `historical_population` — what are the 9 data points? Time intervals? Need to check structure (array of values? array of {date, value}?).
- [ ] `current_research.progress` threshold — what value means "research complete"? Needs game data (`common/advances/` or `common/defines/`).
- [ ] Unit type max strength — parse `common/unit_types/` to build `{type_key: max_strength}` lookup for accurate deployed manpower calculation.
- [ ] Advance classification — parse `common/advances/` to classify each advance by domain (scientific, social, military, economic…). One-shot at startup; enables grouped advance display and research strategy analysis.
- [ ] Societal values visualization strategy — 16 slider values tracked over time. Best approach: radar chart per snapshot (filtering -999 N/A values) + per-slider trend lines? Decide during frontend design phase.
- [x] ~~Age transition dates~~ → Confirmed universal: Age of Traditions → Renaissance 1342, then 1437/1537/1637/1737 (pattern 1x37 from age 3). Score resets to 0 at each transition. `score.age_score[n]` holds the cumulative score earned in age n.
