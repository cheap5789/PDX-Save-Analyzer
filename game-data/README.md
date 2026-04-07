# game-data/

> **Development convenience only.** The production app reads game files directly from the user's game install directory (configured at startup). This folder is used solely by the Toolbox scripts during development.

**This entire directory is git-ignored and must never be committed or published.**
The files here are copyright Paradox Interactive.

---

## EU5 — Setup

Copy the entire `game/` folder from your EU5 Steam installation into `game-data/` and rename it to `eu5`:

```
Source:      C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\
Destination: game-data/eu5\
```

### Resulting structure (top level)

```
game-data/eu5/
  in_game/          ← game logic, configs, unit definitions
  main_menu/        ← localization lives here (see note below)
  dlc/              ← DLC data
  loading_screen/
  mod/
```

### What the parser actually uses

| Path | Contents | Used for |
|------|----------|----------|
| `eu5/in_game/common/unit_types/` | 29 `.txt` files | Military extraction — maps unit type keys to categories (infantry, cavalry, …) and max strength |
| `eu5/in_game/common/cultures/` | 52 `.txt` files | Culture display names and group membership |
| `eu5/main_menu/localization/english/` | 111 `.yml` files | All in-game display text (countries, cultures, religions, estates, war names, …) |

> **Localization quirk:** there is no `in_game/localization/` folder. All in-game display strings ship under `main_menu/localization/` — this is an EU5 packaging choice, not an error.

---

## Production vs. development

| Context | Where game files come from |
|---------|---------------------------|
| **Production app** | User's game install path (configured at startup via the Config tab). |
| **Toolbox scripts** | This `game-data/` directory. |

---

## Adding other games (future)

Create `game-data/ck3/`, `game-data/hoi4/`, etc. following the same pattern.
