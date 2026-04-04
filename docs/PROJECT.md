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

### [2026-04-04] Snapshot fields are configurable per campaign (curated catalog + toggle)
**Decision:** The app ships with a curated catalog of ~44 known EU5 numeric fields (treasury, manpower, stability, scores, etc.) with JSON paths, types, categories, and default on/off. The user toggles fields via checkboxes in the UI. Only enabled fields are recorded in snapshot rows.
**Rationale:** Balances flexibility (user controls DB size) with simplicity (no manual JSON path entry). The catalog is easily extendable as we discover more fields.
**Detail:** See `backend/parser/eu5/field_catalog.py` for the full registry.

### [2026-04-04] Event detection uses summary diffing
**Decision:** On each save parse, a compact summary object is extracted (ruler, wars, alliances, culture, religion, rank, age, situations). Two summaries are diffed to produce typed events. Summaries are ephemeral — only events are stored.
**Rationale:** The full save JSON is ~136MB. Diffing it entirely is impractical. Summary diffing is fast, deterministic, and the summary definition is extensible. Adding a new detectable event means adding a field to the summary and a diff clause.
**Detail:** See `backend/parser/eu5/summary.py` and `backend/parser/eu5/events.py`.

### [2026-04-04] Core parser modules promoted from toolbox to backend
**Decision:** `save_loader.py` and `localisation.py` moved to `backend/parser/`. Toolbox scripts retain thin re-export wrappers so existing CLI usage and notebooks don't break.
**Rationale:** The parser is a backend concern; keeping it in toolbox would create a circular dependency when the watcher and API import it.

### [2026-04-04] File watcher uses completion-marker debounce
**Decision:** The watchdog-based file watcher doesn't trigger immediately on file change. It monitors the file size at 0.5s intervals and only emits the path once the size has been stable for 2 seconds. This handles EU5's large saves (~34MB) which take several seconds to write.
**Rationale:** User chose "completion marker" over simpler debounce. Polling file size stability is OS-agnostic and more reliable than file-lock detection for cross-platform use.

### [2026-04-04] Watcher ignores pre-existing saves by default
**Decision:** On startup the pipeline records a UTC timestamp. Any save file whose modification time is older than this timestamp is silently skipped. Only saves written *after* the watcher starts are processed.
**Rationale:** Prevents accidental bulk-processing of a directory full of old saves on first launch. A "backfill / reprocess" option can be added later as an explicit opt-in.

### [2026-04-04] Full stack is async from the start
**Decision:** The watcher pipeline, database layer, and file watcher all use asyncio + aiosqlite. The pipeline runs as an asyncio task that can be embedded directly into FastAPI in Phase 4.
**Rationale:** Avoids a sync→async rewrite in Phase 4. aiosqlite is already a dependency.

### [2026-04-04] Minimal REST + WebSocket API (Phase 4)
**Decision:** The API layer is a thin REST + WebSocket skin over the existing pipeline. REST endpoints expose CRUD for playthroughs, snapshots, events, and the field catalog. A single `/ws` endpoint pushes live updates (snapshots, events, status changes) to all connected clients.
**Rationale:** No GraphQL or gRPC complexity needed. REST handles queries; WebSocket handles push. The frontend is the only consumer.

### [2026-04-04] Frontend-triggered start (Phase 4)
**Decision:** The server boots idle. The frontend sends `POST /api/start` with config (game install path, save directory, frequency, language, enabled fields) to launch the watcher pipeline. `POST /api/stop` tears it down.
**Rationale:** User chose frontend-triggered over auto-start. This keeps the backend stateless on boot and lets the React UI own the configuration flow — matching the existing design decision that a startup UI is always required before the watcher activates.

### [2026-04-04] Dashboard: single-page with tabs, Tailwind CSS, Recharts (Phase 5)
**Decision:** The React dashboard is a single-page app with four tabs: Overview, Charts, Events, Config. Styled with Tailwind CSS utility classes (no component library). Line charts via Recharts for all time-series data. Dark theme matching the Paradox aesthetic.
**Rationale:** User chose simplicity over complexity at every decision point. Single-page avoids routing overhead. Tailwind is fast to prototype. Line-only charts cover the primary use case (tracking numeric fields over game time).

### [2026-04-04] Auto-reconnect on page load (Phase 5)
**Decision:** On page load, the frontend calls `GET /api/status`. If a pipeline is running, it connects WebSocket and shows live data immediately. If not, it defaults to the Config tab.
**Rationale:** Matches the "auto-resume" design decision. Players refreshing the browser mid-session shouldn't lose their live feed.

### [2026-04-04] Country comparison: picker + overlay (Phase 5)
**Decision:** Country comparison uses a checkbox picker (up to 8 countries). Selected countries are overlaid as separate colored lines on the same Recharts chart. No side-by-side panels.
**Rationale:** Overlay is the most space-efficient comparison method and the most natural for time-series data. 8-country cap keeps charts readable.

### [2026-04-04] Event log: chronological feed with type filter (Phase 5)
**Decision:** Events displayed as a scrollable card feed, newest first. Each card shows an icon, event type, game date, and payload summary. Filter buttons for each event type with counts.
**Rationale:** Simple and functional. Timeline view deferred — can be added later without restructuring.

### [2026-04-04] AAR notes: inline per event (Phase 6)
**Decision:** Each event card has an "Add note" / "Edit note" button that expands an inline text editor. Notes are saved via `PATCH /api/events/{id}/note` to the existing `aar_note` column. Historical events (with notes) are loaded from REST on tab open and merged with live WebSocket events.
**Rationale:** User chose the simplest option. A separate AAR journal or export can be layered on later without restructuring the event model.

### [2026-04-04] Config persistence: game-keyed, data/{game}_config.json (Phase 6)
**Decision:** Config is saved per game as `data/{game}_config.json` (e.g. `data/eu5_config.json`). `POST /api/config` saves config without starting the pipeline. `GET /api/config?game=eu5` loads it. On `POST /api/start`, config is also persisted automatically.
**Rationale:** Minimal friction. User doesn't need to re-enter paths every session. Game-keyed files prepare for multi-game support. The file is already in `.gitignore`.

### [2026-04-04] ConfigTab redesign: 3 action buttons, browse mode, all fields enabled
**Decision:** ConfigTab has three action buttons: Save Config (always available when not running), Start Pipeline (when stopped), Stop Pipeline (when running). A playthrough picker loads historical data without running the pipeline ("browse mode"). All 44 fields default to enabled. Config is game-scoped (EU5 hardcoded for now).
**Rationale:** Decoupling "save config" from "start pipeline" lets users adjust settings without committing to a run. Browse mode lets users review past campaign data. All-fields-on by default avoids the "empty dashboard" experience — users can disable what they don't want rather than enabling what they do.

### [2026-04-04] Localisation enriches all event payloads and snapshots
**Decision:** Summary extraction and event diffing now populate display-name fields alongside raw keys. Countries get `country_display`, `culture_display`, `religion_display`. Wars get `name_display`. Ages get `current_age_display`. Event payloads include both `from_religion_key` and `from_religion` (display name). Snapshots include `current_age_display`.
**Rationale:** The frontend should never need to do its own key→display-name resolution. Display names are computed once at parse time using the localisation dict already loaded into `EU5Save`.

### [2026-04-04] Single-action startup script (start.ps1)
**Decision:** A PowerShell script (`start.ps1`) activates the venv, checks/installs Python and Node dependencies, starts the FastAPI backend and Vite dev server as background jobs, opens the browser, and streams logs. A companion `start.bat` wraps it for double-click use. `Ctrl+C` tears everything down.
**Rationale:** Eliminates the multi-terminal juggle of "activate venv → python run_server.py → cd frontend → npm run dev → open browser".

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
| 2 | Rakaly integration + EU5 parser | ✅ Complete |
| 3 | File watcher + SQLite storage | ✅ Complete |
| 4 | FastAPI backend + WebSocket | ✅ Complete |
| 5 | React dashboard — stats, charts, event log | ✅ Complete |
| 6 | AAR event notes, config persistence | ✅ Complete |
| 7 | Second game (TBD) | ⏳ Next |

---

## Resolved Questions

- [x] Does `rakaly CLI json` correctly decode EU5 `.eu5` binary saves? **Yes.** rakaly v0.8.14 outputs clean JSON. Confirmed 2026-04-03.
- [x] Where are EU5 base game config files located? **`<install>/game/`** for common/events/setup. **`<install>/game/main_menu/localization/`** for localisation. Confirmed 2026-04-04.
- [x] How do numeric IDs (culture, religion) in the save map to string keys? **The save is self-referential.** `culture_manager.database[id]` and `religion_manager.database[id]` within the save itself provide the int→string mapping. Localisation files are only needed for display names. Confirmed 2026-04-03.

## Open Questions

- [ ] Which EU5 `currency_data` fields correspond to which game mechanics? (e.g. `karma`, `purity`, `righteousness` — religion-specific?) Needs `common/defines/` or game documentation.
- [ ] What is the stability scale in EU5? (Observed value: 23.09 — is this 0–100? Different from EU4's -3 to +3?)
- [ ] What are all the detectable events we can diff between saves? (Ruler death, war start/end, crisis — need to map which save keys change.)
