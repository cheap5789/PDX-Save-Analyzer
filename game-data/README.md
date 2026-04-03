# game-data/

This directory holds proprietary base game files copied from your local EU5 (and future game) installations.

**This entire directory is git-ignored and must never be committed or published.**
The files here are copyright Paradox Interactive.

---

## EU5 — What to copy and from where

Default EU5 install path (Steam):
```
C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\
```

Copy the following into `game-data/eu5/`, preserving the subfolder structure:

### Priority 1 — needed for toolbox & parser

| Source path (relative to `game/`) | Purpose |
|-----------------------------------|---------|
| `common/country_tags/` | Tag → country name mapping |
| `common/countries/` | Country definitions |
| `common/cultures/` | Culture ID → name |
| `common/religions/` | Religion ID → name |
| `common/ages/` | Age definitions (age_3_discovery etc.) |
| `localisation/english/` | Display name strings for everything |

### Priority 2 — needed for event detection

| Source path | Purpose |
|-------------|---------|
| `common/governments/` | Government type definitions |
| `common/technologies/` | Tech tree definitions |
| `events/` | Event definitions (for event type labelling) |

### Priority 3 — map & province data (Phase 2)

| Source path | Purpose |
|-------------|---------|
| `map/provinces.bmp` | Province colour map |
| `map/definition.csv` | Province ID → colour → name |
| `common/province_types/` | Province type definitions |

---

## Adding other games (future)

Create `game-data/ck3/`, `game-data/hoi4/`, etc. following the same pattern.
