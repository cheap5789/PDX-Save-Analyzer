# Toolbox — Save Game Data Explorer

The Toolbox is a set of standalone scripts used to empirically understand Paradox save file formats **before** writing any parser. It was built in Phase 1.

---

## Purpose

- Explore the raw structure of a save file
- Identify what keys exist, their types, and sample values
- Discover relationships between objects (culture/religion ID → name, country ID → TAG)
- Resolve display names via localisation files
- Populate `docs/games/<game>/` with verified, cited findings

---

## Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `toolbox/save_loader.py` | Core loader — calls rakaly CLI, builds lookup tables, returns `EU5Save` dataclass | ✅ Complete |
| `toolbox/localisation.py` | Parses EU5 `.yml` localisation files into a flat key→display name dict | ✅ Complete |
| `toolbox/explore.py` | Interactive CLI browser — navigate JSON tree, resolve culture/religion IDs inline | ✅ Complete |
| `toolbox/schema_dump.py` | Dump key tree with types and sample values to JSON (supports `--section` and `--depth`) | ✅ Complete |
| `toolbox/find_key.py` | Recursive key search across entire save — substring or exact match | ✅ Complete |

---

## Core: `save_loader.py`

> **Module location note (2026-04-04):** `save_loader.py` and `localisation.py` were promoted from `toolbox/` to `backend/parser/` so the watcher and API can import them without a circular dependency. `toolbox/save_loader.py` and `toolbox/localisation.py` remain as **thin re-export wrappers** so the toolbox CLI commands and notebooks continue to work unchanged. All real logic lives in `backend/parser/save_loader.py` and `backend/parser/localisation.py`.

All other scripts depend on `save_loader.load_save()`. It returns an `EU5Save` dataclass with:

- `raw` — full rakaly JSON output
- `culture_index` — int id → culture key (from `culture_manager.database`)
- `religion_index` — int id → religion key (from `religion_manager.database`)
- `tag_index` — numeric string → 3-letter TAG (from `countries.tags`)
- `loc` — localisation key → display name (if `--loc` provided)

Key methods: `resolve_culture(id)`, `resolve_religion(id)`, `resolve_culture_name(id)`, `resolve_religion_name(id)`, `country_tag(id)`, `country_display_name(tag)`, `player_country_data()`, `all_real_countries()`.

---

## Usage

All scripts use `-m` module syntax from the project root:

```bash
# Interactive browser with localisation
python -m toolbox.explore saves/autosave.eu5 --loc game-data/eu5/localization/english

# Dump schema to file (depth 4)
python -m toolbox.schema_dump saves/autosave.eu5 --out docs/games/eu5/schema.json --depth 4

# Dump a specific section
python -m toolbox.schema_dump saves/autosave.eu5 --section countries.database.2186 --depth 6 --pretty

# Search for a key (substring match, max 50 results)
python -m toolbox.find_key saves/autosave.eu5 treasury

# Exact match search
python -m toolbox.find_key saves/autosave.eu5 war_exhaustion --exact --max 20
```

### Rakaly binary location

All scripts default to `--rakaly bin/rakaly/rakaly`. The project ships with rakaly v0.8.14 binaries in `bin/rakaly/` (git-ignored).

### Localisation directory

For development, localisation files are copied to `game-data/eu5/localization/english/` (git-ignored). The production app reads directly from the game install — see `docs/CONFIGURATION.md`.

---

## Output

Phase 1 toolbox findings are documented in:

- `docs/games/eu5/save-schema.md` — complete save format documentation
- `docs/games/eu5/OVERVIEW.md` — verified game concepts and config file locations
- `docs/games/eu5/schema_top_level.json` — generated schema dump
