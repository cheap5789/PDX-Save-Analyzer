# Toolbox — Save Game Data Explorer

The Toolbox is a set of standalone scripts used to empirically understand Paradox save file formats **before** writing any parser. It is Phase 1 of the build order.

---

## Purpose

- Explore the raw structure of a save file
- Identify what keys exist, their types, and sample values
- Discover relationships between objects
- Cross-reference save keys with base game config files
- Populate `docs/games/<game>/` with verified, cited findings

---

## Scripts (planned)

| Script | Purpose |
|--------|---------|
| `toolbox/explore.py` | Interactive key browser — navigate the JSON tree from a rakaly-decoded save |
| `toolbox/schema_dump.py` | Dump the full key tree (keys only, no values) to a JSON file for offline review |
| `toolbox/find_key.py` | Search for a specific key across the entire save, print path + sample value |
| `toolbox/link_config.py` | Cross-reference save keys with a base game config file directory |
| `toolbox/inspect_raw.py` | Low-level binary inspector for the pre-ZIP and gamestate sections |

---

## Usage (once built)

```bash
# Explore interactively
python toolbox/explore.py path/to/save.eu5

# Dump full schema
python toolbox/schema_dump.py path/to/save.eu5 --out docs/games/eu5/schema_dump.json

# Find a key
python toolbox/find_key.py path/to/save.eu5 --key treasury

# Cross-reference with config
python toolbox/link_config.py path/to/save.eu5 --config-dir "C:/Steam/steamapps/common/EU5/game/common/"
```

---

## Status

- [ ] `inspect_raw.py` — format already analyzed manually (see `docs/games/eu5/save-schema.md`)
- [ ] `explore.py` — blocked on rakaly CLI EU5 support verification
- [ ] `schema_dump.py` — blocked on rakaly CLI EU5 support verification
- [ ] `find_key.py` — blocked on rakaly CLI EU5 support verification
- [ ] `link_config.py` — blocked on EU5 install path + config file locations
