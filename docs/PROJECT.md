# PDX Save Analyzer — Project Documentation

> Living document. Update this file whenever a design decision is made, revised, or reversed.
> Format: `[YYYY-MM-DD] Decision — Rationale`

---

## Project Goal

A live watcher and analyzer for Paradox games. The tool watches the save games directory, extracts data using Rakaly, and presents it in a configurable web UI. Key features: live snapshot of current game state, multi-country comparison, time-series history across saves, and event detection (ruler deaths, wars, crises) suitable for AAR (After Action Report) material.

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend language | Python | Ease of prototyping, watchdog for file watching, FastAPI for web server |
| Web framework | FastAPI | Async support, WebSocket native, fast |
| File watcher | watchdog | Event-driven, cross-platform, low overhead |
| Save parser | rakaly CLI v0.8.14 (subprocess) | Handles binary Jomini format; outputs JSON to stdout. Confirmed working on EU5. |
| Real-time comms | WebSockets | Backend pushes updates instantly on new save detection |
| Frontend | React + Vite | Component-based, Recharts for time series, good ecosystem |
| Storage | SQLite | Time series snapshots + event log; no external dependencies |

---

## Design Decisions

### [2026-04-03] Game priority: EU5 first, others blocked
**Decision:** Build and validate the full stack for EU5 before touching any other game (CK3, Victoria 3, HOI4, Imperator).
**Rationale:** User has the most material for EU5; de-risking the pipeline on one game before generalizing avoids over-engineering.

### [2026-04-03] Toolbox-first approach
**Decision:** Before writing any parser or dashboard code, build a Toolbox — a set of exploration scripts to empirically understand the save format.
**Status:** ✅ Complete. Toolbox built and tested (Phase 1). Findings documented in `docs/games/eu5/save-schema.md`.

### [2026-04-03] Documentation rule: never assume object semantics
**Decision:** No object, key, or field in a save file gets a semantic label in the parser until the corresponding base game config file has been found and cited.
**Rationale:** Paradox game saves have thousands of fields. Wrong assumptions propagate silently and corrupt downstream data and charts.

### [2026-04-03] One database file per game, campaigns distinguished by playthrough_id
**Decision:** Each game gets its own SQLite file (`data/eu5.db`, `data/ck3.db`, etc.). Within a game DB, campaigns are separated by `playthrough_id` (UUID from save metadata). Three tables: `playthroughs`, `snapshots`, `events`.
**Rationale:** Games have incompatible schemas. One DB per game keeps schemas clean and files manageable. The UUID is already in every save (`metadata.playthrough_id`), making it a natural primary key.
**Detail:** See `docs/CONFIGURATION.md`.

### [2026-04-03] Playthrough switching detected automatically via playthrough_id
**Decision:** The watcher reads `metadata.playthrough_id` from every save. A change in UUID means the player switched campaigns. The watcher handles this silently: closes the old playthrough, opens or resumes the new one, logs a system event. No UI interaction needed.
**Rationale:** Players can switch from one campaign to another mid-session (e.g. close Prussia, open Spain). The UUID is reliable and already present in every save — no heuristics needed.
**Context:** SP campaigns (~50h total) and MP campaigns (4–5h sessions, weeks/months of real time) often coexist. Only one game instance runs at a time, so simultaneous save files from different campaigns cannot occur.

### [2026-04-03] Snapshot frequency is changeable mid-campaign at zero cost
**Decision:** Frequency is a threshold applied at parse time, not a schema constraint. Changing it takes effect on the next detected save with no migration or performance impact.
**Rationale:** No technical reason to lock it. Useful if a player wants finer granularity during a critical period and coarser outside of it.

### [2026-04-03] On app restart: propose auto-resume, user confirms
**Decision:** If a previously active playthrough exists for the configured game + directory, the startup UI proposes to resume it. The user can confirm or start a new session.
**Rationale:** MP campaigns run over weeks. Forcing full reconfiguration each session is unnecessary friction.

### [2026-04-03] Startup configuration UI required before watcher starts
**Decision:** A configuration step is always presented before the watcher activates. Required input: game install path, save directory, snapshot frequency. Country, multiplayer flag, and playthrough ID are auto-detected from the first save.
**Rationale:** The watcher behaviour (which DB to write to, what frequency to snapshot) depends entirely on session context. Hardcoding any of this would break multi-campaign or multi-game use.
**Detail:** See `docs/CONFIGURATION.md`.

### [2026-04-03] Snapshot recording and event detection are decoupled
**Decision:** Event detection runs on every save file change. Snapshot recording only runs when the in-game date crosses the configured frequency threshold (yearly, 5-yearly, etc.).
**Rationale:** A ruler death or war start must never be missed even if the snapshot frequency is coarse. Events are stored in their own table with their precise in-game date regardless of snapshot cadence.
**Detail:** See `docs/CONFIGURATION.md`.

### [2026-04-03] Map view deferred to Phase 2
**Decision:** Political/province map visualization is out of scope for Phase 1.
**Rationale:** Requires significant additional work (SVG/canvas rendering, province geometry data per game). Focus on stats, charts, and events first.

### [2026-04-03] Git workflow: feature branches + commits
**Decision:** One branch per feature phase. Commits at meaningful milestones. User controls merges to main via GitHub Desktop.
**Note:** Git operations are performed on the Windows host (GitHub Desktop), not from the development sandbox.
**Commit format:** `feat(eu5): ...` / `fix(watcher): ...` / `docs: ...` / `toolbox: ...`

### [2026-04-04] Localisation read directly from game install, not shipped with the app
**Decision:** The app reads localisation `.yml` files at runtime from `<EU5 install>/game/main_menu/localization/<language>/`. No proprietary game files are stored in or shipped with the project.
**Rationale:** Always in sync with game patches, supports user's language automatically, no proprietary files in the project. A processed cache (`data/eu5_loc_cache.json`) is built on first run and invalidated when the game version changes.
**Detail:** See `docs/CONFIGURATION.md` — Localisation Strategy section.

---

## Build Phases

| Phase | Name | Status |
|-------|------|--------|
| 0 | Git init + project scaffold + docs | ✅ Complete |
| 1 | Toolbox — save explorer, schema dumper, key finder | ✅ Complete |
| 2 | Rakaly integration + EU5 parser | ⏳ Next |
| 3 | File watcher + SQLite storage | ⏳ Pending |
| 4 | FastAPI backend + WebSocket | ⏳ Pending |
| 5 | React dashboard — stats, charts, event log | ⏳ Pending |
| 6 | AAR event notes, config persistence | ⏳ Pending |
| 7 | Second game (TBD) | ⏳ Blocked until Phase 6 done |

---

## Resolved Questions

- [x] Does `rakaly CLI json` correctly decode EU5 `.eu5` binary saves? **Yes.** rakaly v0.8.14 outputs clean JSON. Confirmed 2026-04-03.
- [x] Where are EU5 base game config files located? **`<install>/game/`** for common/events/setup. **`<install>/game/main_menu/localization/`** for localisation. Confirmed 2026-04-04.
- [x] How do numeric IDs (culture, religion) in the save map to string keys? **The save is self-referential.** `culture_manager.database[id]` and `religion_manager.database[id]` within the save itself provide the int→string mapping. Localisation files are only needed for display names. Confirmed 2026-04-03.

## Open Questions

- [ ] Which EU5 `currency_data` fields correspond to which game mechanics? (e.g. `karma`, `purity`, `righteousness` — religion-specific?) Needs `common/defines/` or game documentation.
- [ ] What is the stability scale in EU5? (Observed value: 23.09 — is this 0–100? Different from EU4's -3 to +3?)
- [ ] What are all the detectable events we can diff between saves? (Ruler death, war start/end, crisis — need to map which save keys change.)
