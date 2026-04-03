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
  ├─ Extract ZIP (Python zipfile, offset = first PK\x03\x04 signature)
  │    ├─ gamestate  → Jomini binary → needs rakaly CLI or token table
  │    └─ string_lookup → parse length-prefixed string list
  │
  └─ [Option A] rakaly CLI json <file> → JSON stdout (preferred, needs EU5 support verification)
     [Option B] librakaly via ctypes (fallback)
     [Option C] custom token decoder (only if rakaly doesn't support EU5)
```

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

## Open Questions / Next Steps

- [ ] Resolve `primary_culture` numeric ID → name (needs `common/cultures/` config)
- [ ] Resolve `primary_religion` numeric ID → name (needs `common/religions/` config)
- [ ] Resolve `capital` location ID → province name (needs `map/` or `common/` config)
- [ ] Confirm meaning of `stability` scale (23.09 — is this 0–100? needs config)
- [ ] Confirm `karma` / `purity` / `righteousness` — which religion mechanics use which?
- [ ] Find display name mapping for country tags (WUR → "Württemberg"?) via localisation
- [ ] Understand `age_3_discovery` — what ages exist and what are their thresholds?
- [ ] Locate EU5 base game install directory to find config files
