# PDX Save Analyzer — Application Map

> **Purpose.** This document is the architecture reference for PDX Save Analyzer. It is **file-level** by design — every node corresponds to a real file in the repository — so it can be used as a debugging map: when something misbehaves, find the file in a diagram, follow the arrows to its callers and callees, and you have the blast radius.
>
> **Maintenance rule (project rule #2).** Every change to the file layout, dependency edges, API surface, DB schema, or runtime flow must be reflected here in the same change. If a diagram and the code disagree, the code is right and this doc is a bug. Do not let it drift.
>
> **Scope.** Game-agnostic where possible; EU5-specific where the implementation only covers EU5 today (the entire `backend/parser/eu5/` subtree).
>
> **How to read the diagrams.** Boxes are files. Solid arrows are static `import` edges (`A → B` means *A imports B*). Dashed arrows are runtime data flow or function calls across an async / IPC boundary. Subgraph boxes are folders. Where a folder contains too many files to be useful inline, the inline diagram shows folder-level nodes and a dedicated zoom-in section follows.

---

## 1. High-Level Layers

```mermaid
flowchart TD
    user([User])
    game[(EU5 game<br/>writes .eu5 saves)]
    install[(EU5 install<br/>game-data + map_data + localization)]

    subgraph entry["Entry points"]
        run_server["run_server.py"]
        run_watcher["run_watcher.py<br/><i>(dev only)</i>"]
        start_bat["start.bat / start.ps1"]
    end

    subgraph backend["Backend (Python, FastAPI + asyncio)"]
        api["backend/api/<br/>FastAPI routes + WS"]
        watcher["backend/watcher/<br/>pipeline + file watcher + backfill"]
        parser["backend/parser/<br/>save loader + EU5 extractors + localisation"]
        storage["backend/storage/<br/>SQLite (aiosqlite)"]
        config["backend/config.py<br/>SessionConfig"]
    end

    subgraph rakaly["External tool"]
        rakaly_bin["bin/rakaly/rakaly<br/>(binary save → JSON)"]
    end

    db[("data/eu5.db<br/>SQLite")]

    subgraph frontend["Frontend (React + Vite + Tailwind)"]
        app["App.jsx + tabs/*"]
        contexts["contexts/*<br/>GameLocalization, CountryNames, Perf, Abort"]
        hooks["hooks/*<br/>useApi, useWebSocket, usePerfTracker"]
    end

    user -->|plays| game
    game -->|writes saves| install
    user -->|opens browser| frontend

    start_bat --> run_server
    run_server --> api

    api --> watcher
    api --> storage
    watcher --> parser
    watcher --> storage
    parser --> rakaly_bin
    rakaly_bin -.->|JSON stdout| parser
    parser -.->|reads localisation + map_data + unit_types| install
    storage --> db

    api -. REST + WebSocket .-> hooks
    hooks --> app
    contexts --> app
```

The `entry → backend` and `backend → db` edges are strict; the `backend → frontend` edges happen over the network (REST + a single WebSocket on `/ws`). The frontend never reads the SQLite file directly.

---

## 2. Backend — File-Level Module Dependencies

This is the single most useful diagram for backend debugging. Every backend `.py` file is a node; every `from backend.X import Y` is an edge.

```mermaid
flowchart LR
    classDef entry fill:#fde68a,stroke:#92400e,color:#000
    classDef api fill:#bfdbfe,stroke:#1e40af,color:#000
    classDef watcher fill:#fecaca,stroke:#991b1b,color:#000
    classDef parser fill:#bbf7d0,stroke:#166534,color:#000
    classDef eu5 fill:#d9f99d,stroke:#3f6212,color:#000
    classDef storage fill:#e9d5ff,stroke:#6b21a8,color:#000
    classDef cfg fill:#fef3c7,stroke:#78350f,color:#000

    %% --- Entry points ---
    runserver["run_server.py"]:::entry
    runwatcher["run_watcher.py"]:::entry

    %% --- Config ---
    cfg["config.py<br/>SessionConfig"]:::cfg

    %% --- API ---
    api_app["api/app.py<br/>FastAPI() + CORS"]:::api
    api_routes["api/routes.py<br/>~30 endpoints + /ws"]:::api
    api_schemas["api/schemas.py<br/>Pydantic models"]:::api

    %% --- Watcher ---
    pipeline["watcher/pipeline.py<br/>WatcherPipeline"]:::watcher
    file_watcher["watcher/file_watcher.py<br/>watchdog observer"]:::watcher
    backfill["watcher/backfill.py<br/>historical replay"]:::watcher

    %% --- Parser core ---
    save_loader["parser/save_loader.py<br/>load_save() + EU5Save"]:::parser
    loc["parser/localisation.py<br/>load_localisation +<br/>load_geo_localisation"]:::parser

    %% --- Parser EU5 extractors ---
    field_catalog["eu5/field_catalog.py<br/>121 FieldDef entries"]:::eu5
    snapshot_x["eu5/snapshot.py<br/>extract_snapshot"]:::eu5
    summary_x["eu5/summary.py<br/>extract_summary"]:::eu5
    events_x["eu5/events.py<br/>diff_summaries"]:::eu5
    countries_x["eu5/countries.py<br/>extract_country_rows"]:::eu5
    cultures_x["eu5/cultures.py<br/>extract_culture_statics"]:::eu5
    religions_x["eu5/religions.py<br/>religions + religion_snapshots"]:::eu5
    wars_x["eu5/wars.py<br/>wars + participants + battles"]:::eu5
    military_x["eu5/military.py<br/>country military + sieges"]:::eu5
    geography_x["eu5/geography.py<br/>locations + provinces +<br/>detect_location_events"]:::eu5
    geo_index["eu5/geography_index.py<br/>parses definitions.txt"]:::eu5
    demographics_x["eu5/demographics.py<br/>extract_pop_snapshot_rows"]:::eu5
    save_meta["eu5/save_metadata.py"]:::eu5
    game_date["eu5/game_date.py<br/>should_snapshot"]:::eu5

    %% --- Storage ---
    db["storage/database.py<br/>Database (aiosqlite)"]:::storage

    %% --- Edges: entry ---
    runserver --> api_app
    runwatcher --> pipeline
    runwatcher --> cfg

    %% --- API edges ---
    api_app --> api_routes
    api_routes --> api_schemas
    api_routes --> cfg
    api_routes --> field_catalog
    api_routes --> events_x
    api_routes --> db
    api_routes --> pipeline

    %% --- Watcher edges ---
    pipeline --> cfg
    pipeline --> save_loader
    pipeline --> file_watcher
    pipeline --> field_catalog
    pipeline --> snapshot_x
    pipeline --> summary_x
    pipeline --> events_x
    pipeline --> religions_x
    pipeline --> cultures_x
    pipeline --> countries_x
    pipeline --> wars_x
    pipeline --> military_x
    pipeline --> geography_x
    pipeline --> geo_index
    pipeline --> demographics_x
    pipeline --> game_date
    pipeline --> db

    backfill --> save_loader
    backfill --> field_catalog
    backfill --> snapshot_x
    backfill --> religions_x
    backfill --> cultures_x
    backfill --> wars_x
    backfill --> military_x
    backfill --> geography_x
    backfill --> geo_index
    backfill --> demographics_x
    backfill --> countries_x
    backfill --> db

    %% --- Parser-internal edges ---
    snapshot_x --> save_loader
    snapshot_x --> field_catalog
    summary_x --> save_loader
    events_x --> summary_x
    countries_x --> save_loader
    cultures_x --> save_loader
    cultures_x --> loc
    religions_x --> save_loader
    wars_x --> save_loader
    wars_x --> loc
    military_x --> save_loader
    geography_x --> save_loader
    geography_x --> geo_index
    demographics_x --> save_loader

    %% --- Implicit external read edges (dashed) ---
    save_loader -. subprocess .-> rakaly[/"bin/rakaly/rakaly"/]
    save_loader -. reads .-> loc
    geo_index -. reads .-> mapdata[/"&lt;install&gt;/game/map_data/<br/>definitions.txt"/]
    loc -. reads .-> locdir[/"&lt;install&gt;/game/main_menu/<br/>localization/&lt;lang&gt;/*.yml"/]
    military_x -. reads .-> unitdir[/"&lt;install&gt;/game/common/<br/>unit_types/*.txt"/]
```

Notable things to read off this graph:

- `pipeline.py` and `backfill.py` are the **two** orchestrators. Every EU5 extractor is called from one or both — if a parser bug only shows up live-but-not-on-backfill (or vice-versa) the missing edge in this graph is your first suspect.
- `save_loader.py` is the only file that touches the rakaly subprocess. If saves stop loading, look there first.
- `geo_index.py`, the localisation loader, and the unit-type loader are the only files that touch the user's game install. They are the entire surface area for project rule #5 ("never ship proprietary game files").
- `field_catalog.py` is imported by `pipeline`, `backfill`, `snapshot`, **and** the API (so the frontend can render the field picker). It is the source of truth for which fields are tracked.
- `api/routes.py` and `pipeline.py` are the two largest files and the two highest-fan-in nodes — almost any change is likely to touch one of them.

---

## 3. Frontend — File-Level Module Dependencies

```mermaid
flowchart LR
    classDef entry fill:#fde68a,stroke:#92400e,color:#000
    classDef ctx fill:#fbcfe8,stroke:#9d174d,color:#000
    classDef hook fill:#bfdbfe,stroke:#1e40af,color:#000
    classDef tab fill:#bbf7d0,stroke:#166534,color:#000
    classDef cmp fill:#e9d5ff,stroke:#6b21a8,color:#000
    classDef util fill:#fef3c7,stroke:#78350f,color:#000

    main["main.jsx"]:::entry
    app["App.jsx"]:::entry

    %% Contexts
    ctx_loc["contexts/<br/>GameLocalizationContext.jsx"]:::ctx
    ctx_country["contexts/<br/>CountryNamesContext.js"]:::ctx
    ctx_perf["contexts/<br/>PerfContext.jsx"]:::ctx
    ctx_abort["contexts/<br/>AbortContext.jsx"]:::ctx

    %% Hooks
    h_api["hooks/useApi.js"]:::hook
    h_ws["hooks/useWebSocket.js"]:::hook
    h_perf["hooks/usePerfTracker.js"]:::hook

    %% Utilities
    util["utils/formatters.js<br/>fmtCountry, euDateToNum,<br/>fmtYearTick, ..."]:::util

    %% Top-level components
    tabbar["components/TabBar.jsx"]:::cmp
    perfpanel["components/PerfPanel.jsx"]:::cmp
    statuscard["components/StatusCard.jsx"]:::cmp
    countrypicker["components/CountryPicker.jsx"]:::cmp
    eventcard["components/EventCard.jsx"]:::cmp

    %% War sub-components
    war_forces["components/wars/<br/>WarForcesChart.jsx"]:::cmp
    war_battle["components/wars/<br/>BattleTable.jsx"]:::cmp
    war_part["components/wars/<br/>ParticipantScoresChart.jsx"]:::cmp

    %% Tabs
    tab_overview["tabs/OverviewTab.jsx"]:::tab
    tab_charts["tabs/ChartsTab.jsx"]:::tab
    tab_events["tabs/EventsTab.jsx"]:::tab
    tab_config["tabs/ConfigTab.jsx"]:::tab
    tab_religions["tabs/ReligionsTab.jsx"]:::tab
    tab_wars["tabs/WarsTab.jsx"]:::tab
    tab_territory["tabs/TerritoryTab.jsx"]:::tab
    tab_demographics["tabs/DemographicsTab.jsx"]:::tab

    main --> app

    %% App composes everything
    app --> h_api
    app --> h_ws
    app --> ctx_country
    app --> ctx_loc
    app --> ctx_perf
    app --> ctx_abort
    app --> perfpanel
    app --> tabbar
    app --> tab_overview
    app --> tab_charts
    app --> tab_events
    app --> tab_config
    app --> tab_religions
    app --> tab_wars
    app --> tab_territory
    app --> tab_demographics

    %% Context internals
    ctx_loc --> h_api
    h_api --> ctx_abort
    h_perf --> ctx_perf
    perfpanel --> ctx_perf

    %% Tab dependencies
    tab_overview --> statuscard
    tab_overview --> eventcard
    tab_overview --> ctx_country
    tab_overview --> util
    tab_overview --> h_perf

    tab_charts --> h_api
    tab_charts --> countrypicker
    tab_charts --> ctx_country
    tab_charts --> util
    tab_charts --> h_perf

    tab_events --> eventcard
    tab_events --> ctx_country
    tab_events --> util
    tab_events --> h_perf
    tab_events --> h_api

    tab_config --> h_api

    tab_religions --> h_api
    tab_religions --> h_perf
    tab_religions --> ctx_loc
    tab_religions --> util

    tab_wars --> h_api
    tab_wars --> ctx_country
    tab_wars --> util
    tab_wars --> h_perf
    tab_wars --> war_forces
    tab_wars --> war_battle
    tab_wars --> war_part

    tab_territory --> h_api
    tab_territory --> h_perf
    tab_territory --> ctx_loc

    tab_demographics --> h_api
    tab_demographics --> h_perf
    tab_demographics --> ctx_country
    tab_demographics --> ctx_loc
    tab_demographics --> util

    %% Sub-component edges
    countrypicker --> ctx_country
    countrypicker --> util
    eventcard --> h_api
    eventcard --> ctx_country
    eventcard --> util
    war_forces --> h_api
    war_forces --> util
    war_part --> h_api
    war_part --> util
    war_battle --> util
```

Things to read off this graph:

- `useApi.js` is the **only** file that calls `fetch`. Any new endpoint adds a method here. It hooks into `AbortContext` so any tab can cancel an in-flight request when the user switches away.
- `GameLocalizationContext` is the single source of truth for ID-to-name resolution (cultures, religions, estates, locations, areas, regions, sub-continents, continents, provinces). Any new "I see a raw ID in the UI" bug starts here.
- `CountryNamesContext` is older / simpler — country tag → display name only — and predates `GameLocalizationContext`. The two should probably merge eventually.
- `usePerfTracker` is opt-in; tabs that have it route their fetch durations into `PerfContext`, which `PerfPanel` reads.

---

## 4. Runtime — Live Save Ingest (the hot path)

This is **the** debugging diagram. When a save lands and "the UI didn't update", trace through here.

```mermaid
sequenceDiagram
    autonumber
    participant Game as EU5 game
    participant FS as Save directory
    participant FW as file_watcher.py<br/>(watchdog Observer)
    participant PL as pipeline.py<br/>WatcherPipeline._run_loop
    participant SL as save_loader.py
    participant RAK as rakaly (subprocess)
    participant EX as eu5/*.py<br/>extractors
    participant DB as storage/database.py
    participant API as api/routes.py
    participant WS as /ws (broadcast)
    participant UI as Frontend tabs

    Game->>FS: writes autosave.eu5
    FS-->>FW: FileModifiedEvent
    FW-->>PL: queue.put(save_path)
    PL->>PL: get_next() → save_path
    Note over PL: skip if mtime → pipeline.started_at

    PL->>SL: load_save(path, rakaly_bin, loc_dir)
    SL->>RAK: subprocess.run(rakaly json save.eu5)
    RAK-->>SL: JSON on stdout
    SL->>SL: build culture/religion/tag indexes<br/>load localisation YAMLs
    SL-->>PL: EU5Save

    PL->>PL: _handle_playthrough(save, pt_id)<br/>(create / resume / switch)

    PL->>EX: extract_summary(save)
    PL->>EX: diff_summaries(prev, curr) → events
    PL->>EX: detect_battle_events(save, prev_battle_state)
    PL->>EX: detect_location_events(save, prev_loc_state)
    PL->>DB: insert_events(pt_id, dicts)
    DB-->>PL: count
    PL-->>API: on_events callback
    API->>WS: broadcast {type: events}

    Note over PL: Snapshot gate

    PL->>DB: snapshot_exists(pt_id, game_date)?
    DB-->>PL: yes/no
    alt already recorded
        PL-->>FS: return (no snapshot work)
    else due
        PL->>EX: extract_snapshot(save, enabled_fields)
        PL->>DB: insert_snapshot → snap_id
        PL-->>API: on_snapshot callback
        API->>WS: broadcast {type: snapshot}

        PL->>EX: extract_religion_statics + snapshot_rows
        PL->>DB: upsert_religion + insert_religion_snapshots

        PL->>EX: extract_war_statics + snapshot_rows + participants
        PL->>DB: upsert_war + insert_war_snapshots + ...

        PL->>EX: extract_country_military(save, unit_type_catalog, active_war_ids)
        PL->>DB: bulk_insert_country_military_snapshots

        PL->>EX: extract_new_battles(save, prev_snapshot_battle_state)
        PL->>DB: upsert_battle (per battle)

        PL->>EX: extract_sieges(save, wp_index)
        PL->>DB: upsert_siege + mark_sieges_inactive

        PL->>EX: extract_location_statics(save, geo_index)
        PL->>EX: extract_location_snapshot_rows(save)
        PL->>EX: extract_province_statics + snapshot_rows
        PL->>DB: bulk_upsert_locations + insert_location_snapshots<br/>+ bulk_upsert_provinces + insert_province_snapshots

        PL->>EX: extract_pop_snapshot_rows(save)
        PL->>DB: insert_pop_snapshots

        PL->>EX: extract_country_rows + extract_culture_statics
        PL->>DB: bulk_upsert_countries + bulk_upsert_cultures
    end

    WS-->>UI: snapshot / events frames
    UI->>API: GET /api/snapshots/{pt_id}<br/>GET /api/events/{pt_id}<br/>...
    API->>DB: SELECT ...
    DB-->>API: rows
    API-->>UI: JSON
```

Common failure patterns and where to look in this diagram:

| Symptom | First place to look |
|---|---|
| "Saves not detected" | Steps 1–3: `file_watcher.py`, save extension list in `SessionConfig.save_extensions()`, `_started_at` mtime gate |
| "Save detected but parse fails" | Step 4–6: `save_loader.py`, rakaly binary path, raw JSON shape |
| "Snapshot skipped" | Snapshot gate alt-block: `snapshot_exists` and `should_snapshot` (frequency = `yearly`/`5years`/etc.) |
| "Tab shows raw IDs instead of names" | Frontend → `GameLocalizationContext`, then back to whichever extractor populates the relevant table |
| "Live works, backfill doesn't" (or vice-versa) | Compare which extractors `pipeline.py` calls vs. which `backfill.py` calls — see §5 |
| "WS connected but UI never updates" | `on_snapshot`/`on_events` callbacks → `_broadcast` in `routes.py` → `useWebSocket.js` reducer in `App.jsx` |

---

## 5. Runtime — Historical Backfill

Same extractors as live, **but** entered from the API as a one-shot job over the user's existing save folder. The crucial difference is the set of `detect_*` functions that the live path runs but the backfill path does **not**.

```mermaid
flowchart TD
    classDef live fill:#bbf7d0,stroke:#166534,color:#000
    classDef back fill:#bfdbfe,stroke:#1e40af,color:#000
    classDef both fill:#fef3c7,stroke:#78350f,color:#000

    api_call["POST /api/playthroughs/{id}/backfill"]
    bf["watcher/backfill.py<br/>scan saves dir → sort by mtime"]
    api_call --> bf

    subgraph live["Live path (pipeline.py)"]
        L_es["diff_summaries → snapshot events"]:::both
        L_be["detect_battle_events"]:::live
        L_le["detect_location_events"]:::live
    end

    subgraph back["Backfill path (backfill.py)"]
        B_es["diff_summaries → snapshot events"]:::both
        B_be["detect_battle_events &lt;NOT WIRED&gt;"]:::back
        B_le["detect_location_events &lt;NOT WIRED&gt;"]:::back
    end

    subgraph shared["Shared extractors (called from both)"]
        s1["snapshot.py / extract_snapshot"]
        s2["religions / cultures / countries"]
        s3["wars / military / battles / sieges"]
        s4["geography statics + snapshots<br/>(geo_index used in both)"]
        s5["demographics / pops"]
    end

    bf --> shared
    bf --> B_es
    bf -.->|skipped today| B_be
    bf -.->|skipped today| B_le

    pipeline["pipeline.py<br/>(live)"] --> shared
    pipeline --> L_es
    pipeline --> L_be
    pipeline --> L_le
```

The two `<NOT WIRED>` boxes are tracked in `docs/games/eu5/save-schema.md` under the **Geography** backlog as `[PARTIAL] Geography events in backfill` and `[PARTIAL] Battle sub-events in backfill`. This diagram is the visual version of that ticket — when it's resolved, both dashed edges become solid and the `[PARTIAL]`s become `[DONE]`.

---

## 6. REST API Surface

Every endpoint exposed by `backend/api/routes.py`, the DB tables it reads/writes, and the frontend file that consumes it. Use this when you want to know "if I change endpoint X, what breaks?".

| Method | Path | Tables touched | Frontend caller |
|---|---|---|---|
| `POST` | `/api/start` | `playthroughs` (via pipeline init) | `ConfigTab.jsx` |
| `POST` | `/api/stop` | — | `ConfigTab.jsx` |
| `GET` | `/api/status` | — (in-memory pipeline state) | `App.jsx`, `ConfigTab.jsx` |
| `GET` | `/api/config` | — (file: `data/session_config.json`) | `ConfigTab.jsx` |
| `POST` | `/api/config` | — (file) | `ConfigTab.jsx` |
| `POST` | `/api/load-playthrough` | `playthroughs` | `ConfigTab.jsx` |
| `GET` | `/api/scan-saves` | — (file system) | `ConfigTab.jsx` |
| `POST` | `/api/playthroughs/{id}/backfill` | all tables (replays into DB) | `ConfigTab.jsx` |
| `GET` | `/api/playthroughs` | `playthroughs` | `App.jsx` |
| `GET` | `/api/snapshots/{id}` | `snapshots` | `ChartsTab.jsx`, `App.jsx` |
| `GET` | `/api/events/{id}` | `events` | `EventsTab.jsx`, `OverviewTab.jsx`, `EventCard.jsx` |
| `GET` | `/api/events/{id}/country-tags` | `events` | `EventsTab.jsx` |
| `GET` | `/api/fields` | — (`field_catalog.py`) | `ConfigTab.jsx` |
| `GET` | `/api/religions/{id}` | `religions` | `GameLocalizationContext`, `ReligionsTab.jsx` |
| `GET` | `/api/religions/{id}/snapshots` | `religion_snapshots` | `ReligionsTab.jsx` |
| `GET` | `/api/cultures/{id}` | `cultures` | `GameLocalizationContext`, `DemographicsTab.jsx` |
| `GET` | `/api/geography/{id}` | `locations` (slugs) + game-data YAMLs | `GameLocalizationContext` |
| `GET` | `/api/wars/{id}` | `wars` | `WarsTab.jsx` |
| `GET` | `/api/wars/{id}/snapshots` | `war_snapshots` | `WarsTab.jsx` → `WarForcesChart.jsx` |
| `GET` | `/api/wars/{id}/participants` | `war_participants` | `WarsTab.jsx` |
| `GET` | `/api/wars/{id}/participant-history` | `war_participant_snapshots` | `WarsTab.jsx` → `ParticipantScoresChart.jsx` |
| `GET` | `/api/battles/{id}` | `battles` | `WarsTab.jsx` → `BattleTable.jsx` |
| `GET` | `/api/sieges/{id}` | `sieges` | `WarsTab.jsx` |
| `GET` | `/api/military/{id}` | `country_military_snapshots` | `WarsTab.jsx` |
| `GET` | `/api/locations/{id}` | `locations` | `TerritoryTab.jsx` |
| `GET` | `/api/locations/{id}/snapshots` | `location_snapshots` **LEFT JOIN** `locations`, `countries` | `TerritoryTab.jsx` |
| `GET` | `/api/provinces/{id}` | `provinces` | *(not yet wired in UI)* |
| `GET` | `/api/provinces/{id}/snapshots` | `province_snapshots` | *(not yet wired in UI)* |
| `GET` | `/api/pops/{id}/snapshots` | `pop_snapshots` | `DemographicsTab.jsx` |
| `GET` | `/api/pops/{id}/aggregates` | `pop_snapshots` (grouped) | `DemographicsTab.jsx` |
| `GET` | `/api/pops/{id}/country-owners` | `pop_snapshots` | `DemographicsTab.jsx` |
| `GET` | `/api/countries/{id}` | `countries` | `DemographicsTab.jsx` |
| `WS` | `/ws` | — (broadcast only) | `useWebSocket.js` |

> When this table drifts, the test is mechanical: `grep -nE "@router\\.(get|post|websocket)" backend/api/routes.py` and `grep -nE "get\\(.*api/" frontend/src/hooks/useApi.js` should each give exactly the rows above.

---

## 7. WebSocket Message Types

The `/ws` endpoint is one-directional (server → client) and broadcasts to every connected client. There are four message types, all wrapped in a `WsMessage{type, data}` envelope.

| `type` | Producer | `data` shape | Frontend consumer |
|---|---|---|---|
| `status` | `broadcast_status()` after `/api/start`, `/api/stop` | `StatusResponse` | `App.jsx` (sets pipeline state) |
| `snapshot` | `pipeline._on_snapshot` callback | snapshot dict | `App.jsx` (triggers tabs to refetch) |
| `events` | `pipeline._on_events` callback | list of event dicts | `App.jsx` → `EventsTab` / `OverviewTab` |
| `backfill_progress` | `backfill.py` job loop | `{stage, current, total, ...}` | `ConfigTab.jsx` progress bar |

---

## 8. SQLite Schema

Every table in `backend/storage/database.py`, grouped by domain. All snapshot tables FK to `snapshots(id)`; everything FKs to `playthroughs(id)`. The composite primary keys on entity tables (`cultures`, `religions`, `wars`, etc.) are `(playthrough_id, id)` so two playthroughs can share the same in-game ID without colliding.

```mermaid
erDiagram
    playthroughs ||--o{ snapshots          : "has"
    playthroughs ||--o{ events             : "has"
    playthroughs ||--o{ religions          : "has"
    playthroughs ||--o{ cultures           : "has"
    playthroughs ||--o{ wars               : "has"
    playthroughs ||--o{ war_participants   : "has"
    playthroughs ||--o{ locations          : "has"
    playthroughs ||--o{ provinces          : "has"
    playthroughs ||--o{ countries          : "has"
    playthroughs ||--o{ battles            : "has"
    playthroughs ||--o{ sieges             : "has"

    snapshots ||--o{ religion_snapshots             : ""
    snapshots ||--o{ war_snapshots                  : ""
    snapshots ||--o{ war_participant_snapshots      : ""
    snapshots ||--o{ country_military_snapshots     : ""
    snapshots ||--o{ location_snapshots             : ""
    snapshots ||--o{ province_snapshots             : ""
    snapshots ||--o{ pop_snapshots                  : ""

    religions ||--o{ religion_snapshots : "FK religion_id"
    wars      ||--o{ war_snapshots      : "FK war_id"
    wars      ||--o{ war_participants   : "FK war_id"
    wars      ||--o{ battles            : "FK war_id"
    wars      ||--o{ sieges             : "FK war_id"
    locations ||--o{ location_snapshots : "FK location_id"
    provinces ||--o{ province_snapshots : "FK province_id"
    locations ||--o{ pop_snapshots      : "FK location_id"
    countries ||--o{ location_snapshots : "owner_id → country_id"

    playthroughs {
        TEXT id PK
        TEXT name
        TEXT game
        TEXT created_at
    }
    snapshots {
        INTEGER id PK
        TEXT playthrough_id FK
        TEXT game_date
        JSON data
    }
    events {
        INTEGER id PK
        TEXT playthrough_id FK
        TEXT game_date
        TEXT event_type
        TEXT country_tag
        JSON payload
        TEXT dedup_key
    }
    locations {
        INTEGER location_id
        TEXT playthrough_id FK
        TEXT slug
        TEXT province_def
        TEXT area
        TEXT region
        TEXT sub_continent
        TEXT continent
        INTEGER province_id
        TEXT raw_material
        BOOL is_port
        JSON holy_sites
    }
    countries {
        TEXT playthrough_id FK
        INTEGER country_id PK
        TEXT tag "NOT unique"
        TEXT name
        TEXT canonical_tag
        JSON prev_tags
    }
    cultures {
        INTEGER id
        TEXT playthrough_id FK
        TEXT definition
        TEXT name
        TEXT culture_group
    }
    religions {
        INTEGER id
        TEXT playthrough_id FK
        TEXT definition
        TEXT religion_group
        TEXT color_rgb
    }
```

(Snapshot tables and per-pop / military tables are omitted from the ER fields list to keep the diagram readable — see `database.py` for the full column list. The full per-table field catalog lives in `docs/games/eu5/save-schema.md`.)

> **Note — `countries.tag` is not unique per playthrough.** Multiple country objects can share a TAG in the same save (formables co-existing with their pre-existing slot, horde civil-war pretenders, etc.). The sole unique handle is `country_id`, and all foreign-key-style joins (e.g. `location_snapshots.owner_id → countries.country_id`) go through it — never through `tag`. See [`docs/games/eu5/duplicate-tags.md`](./games/eu5/duplicate-tags.md) for the empirical finding and decision trail.

---

## 9. Game-Data Read Surface (project rule #5)

These are the **only** places in the codebase that touch the user's game install. Anything new that needs to read from `<install>/...` belongs in one of these modules — never in a tab, never in storage, never committed as a static asset.

```mermaid
flowchart LR
    classDef fs fill:#fde68a,stroke:#92400e,color:#000
    classDef code fill:#bbf7d0,stroke:#166534,color:#000

    install["EU5 install root<br/>(SessionConfig.game_install_path)"]:::fs

    map_data[/"game/map_data/<br/>definitions.txt"/]:::fs
    loc_dir[/"game/main_menu/localization/<br/>&lt;language&gt;/*.yml"/]:::fs
    unit_types[/"game/common/<br/>unit_types/*.txt"/]:::fs
    age_dir[/"game/common/age/"/]:::fs

    install --> map_data
    install --> loc_dir
    install --> unit_types
    install --> age_dir

    geo_index["parser/eu5/<br/>geography_index.py"]:::code
    loc_py["parser/localisation.py<br/>load_localisation +<br/>load_geo_localisation"]:::code
    military_py["parser/eu5/military.py<br/>load_unit_type_catalog"]:::code
    save_loader_py["parser/save_loader.py<br/>(passes loc_dir into rakaly)"]:::code

    map_data --> geo_index
    loc_dir --> loc_py
    loc_dir --> save_loader_py
    unit_types --> military_py

    geo_index --> pipeline["watcher/pipeline.py + backfill.py"]
    loc_py --> pipeline
    military_py --> pipeline
```

The `age/` directory is listed as known-but-not-yet-parsed in `docs/games/eu5/OVERVIEW.md`; when it's wired, a new node belongs on this diagram. Anything not on this diagram is forbidden from reading game files.

---

## 10. Localisation Resolution Chain

How a raw integer or slug in the save becomes a display string in the UI. This is the chain to walk when "the UI shows a number / a slug instead of a name".

```mermaid
flowchart LR
    classDef save fill:#fde68a,stroke:#92400e,color:#000
    classDef be fill:#bbf7d0,stroke:#166534,color:#000
    classDef api fill:#bfdbfe,stroke:#1e40af,color:#000
    classDef fe fill:#e9d5ff,stroke:#6b21a8,color:#000

    save_field["raw save value<br/>(int id or slug)"]:::save

    subgraph savefile["Self-referential lookups (in the save itself)"]
        culture_db[/"culture_manager.database[id]"/]:::save
        religion_db[/"religion_manager.database[id]"/]:::save
        tag_idx[/"countries.tags[id]"/]:::save
        loc_compat[/"metadata.compatibility.<br/>locations[id-1]"/]:::save
    end

    subgraph extr["Extractors store IDs / slugs in DB"]
        cultures_x["cultures.py"]:::be
        religions_x["religions.py"]:::be
        countries_x["countries.py"]:::be
        geography_x["geography.py"]:::be
    end

    subgraph store["SQLite reference tables"]
        cultures_t[(cultures<br/>id → name)]:::be
        religions_t[(religions<br/>id → name)]:::be
        countries_t[(countries<br/>id → tag)]:::be
        locations_t[(locations<br/>id → slug + chain)]:::be
    end

    subgraph yaml["Game install — localisation YAMLs"]
        loc_culture[/"cultural_and_languages_<br/>l_&lt;lang&gt;.yml"/]:::save
        loc_religion[/"religion_l_&lt;lang&gt;.yml"/]:::save
        loc_country[/"countries_l_&lt;lang&gt;.yml"/]:::save
        loc_geo[/"location_names + province_names<br/>+ area_names + region_names<br/>+ continent_l_&lt;lang&gt;.yml"/]:::save
    end

    subgraph apiep["REST endpoints (slim payloads)"]
        api_cult["GET /api/cultures/{pt}"]:::api
        api_rel["GET /api/religions/{pt}"]:::api
        api_geo["GET /api/geography/{pt}"]:::api
    end

    subgraph fe["Frontend contexts + helpers"]
        gctx["GameLocalizationContext.jsx<br/>fmtCulture / fmtReligion / fmtEstate /<br/>fmtLocation / fmtProvince / fmtArea /<br/>fmtRegion / fmtSubContinent / fmtContinent"]:::fe
        cnctx["CountryNamesContext.js<br/>fmtCountry"]:::fe
    end

    save_field --> culture_db
    save_field --> religion_db
    save_field --> tag_idx
    save_field --> loc_compat

    culture_db --> cultures_x
    religion_db --> religions_x
    tag_idx --> countries_x
    loc_compat --> geography_x

    cultures_x --> cultures_t
    religions_x --> religions_t
    countries_x --> countries_t
    geography_x --> locations_t

    cultures_t --> api_cult
    religions_t --> api_rel
    locations_t --> api_geo

    loc_culture -.-> api_cult
    loc_religion -.-> api_rel
    loc_country -.-> countries_t
    loc_geo -.-> api_geo

    api_cult --> gctx
    api_rel --> gctx
    api_geo --> gctx
    countries_t --> cnctx

    gctx --> tabs[["Any tab using<br/>useGameLocalization()"]]
    cnctx --> tabs2[["Any tab using<br/>useCountryNames()"]]
```

Two things to internalise from this diagram:

1. **The save is self-referential for IDs.** Cultures, religions, country tags, and now location slugs are all resolvable from data inside the save itself — `parser/save_loader.py` builds the `culture_index`, `religion_index`, `tag_index` once per parse, and the location slug array is read directly from `metadata.compatibility.locations`. Game files are only needed for the human-readable display string layered on top.
2. **Geography is the only level that needs an external file for the *structural* hierarchy itself**, not just for display strings: `definitions.txt` is what tells us province → area → region → sub_continent → continent. That's why `geography_index.py` exists at all and why it sits in the same trust boundary as the localisation YAMLs.

---

## Maintaining this document

When you change something, here's the checklist:

1. **New backend file** → add a node in §2 and at least one import edge.
2. **New frontend file** → add a node in §3 and the import edges.
3. **New API route** → add a row in §6 and (if applicable) a new WS message in §7.
4. **New DB table or column on a snapshot table** → update §8 and the matching field catalog row in `docs/games/eu5/save-schema.md`.
5. **New file read from the game install** → add a node in §9 (and confirm it's the only place that does it).
6. **New entity type in the save resolved to a display name** → add it to the chain in §10.
7. **New `extract_*` or `detect_*` function** → add it to the live-path sequence in §4 and either to §5's "shared" or to the live-only column.

Per project rule #2, these updates are part of the same change as the code, not a follow-up.
