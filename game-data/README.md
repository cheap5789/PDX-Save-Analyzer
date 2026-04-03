# game-data/

> **Development convenience only.** The production app reads game files directly from the user's game install directory (configured at startup). This folder is used solely by the Toolbox scripts during development.

**This entire directory is git-ignored and must never be committed or published.**
The files here are copyright Paradox Interactive.

---

## EU5 — What to copy and from where

Default EU5 install path (Steam):
```
C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\
```

Copy the following into `game-data/eu5/`, preserving the subfolder structure:

### Game config files (from `game/`)

| Source path (relative to `game/`) | Purpose |
|-----------------------------------|---------|
| `common/` | Country definitions, cultures, religions, ages, technologies, defines |
| `events/` | Event definitions (for event type labelling) |
| `setup/` | Day-0 country state (starting conditions) |

### Localisation (from `game/main_menu/`)

| Source path (relative to `game/`) | Purpose |
|-----------------------------------|---------|
| `main_menu/localization/english/` | Display name strings for all game objects |

> **Note:** The localisation path is `main_menu/localization/` — not `localisation/` or `localization/` at the `game/` root. For the dev copy, place them at `game-data/eu5/localization/english/` for Toolbox convenience.

---

## Production vs. development

| Context | Where game files come from |
|---------|---------------------------|
| **Production app** | User's game install path (configured at startup). See `docs/CONFIGURATION.md`. |
| **Toolbox scripts** | This `game-data/` directory. Pass via `--loc game-data/eu5/localization/english`. |

---

## Adding other games (future)

Create `game-data/ck3/`, `game-data/hoi4/`, etc. following the same pattern.
