# PDX Save Analyzer

A live watcher and analyzer for Paradox grand strategy games.

Watches your save game directory, parses saves, and streams live data to a configurable web dashboard — tracking country stats, time-series history, and key events suitable for After Action Reports.

## Status

🚧 Active development — EU5 (Europa Universalis V) is the first supported game.

## Features

- **Live file watcher** — detects new saves instantly via file system events
- **Multi-campaign support** — tracks SP and MP campaigns simultaneously, auto-detects campaign switches
- **Configurable snapshot frequency** — yearly, every 5 years, etc. to keep the database lean
- **Country stats dashboard** — gold, manpower, stability, prestige, income, population and more
- **Time-series charts** — track any metric across saves with trend lines
- **Event log** — ruler deaths, wars, crises, epidemics — auto-detected, annotatable for AAR writing
- **Wars & military** — participant tracking, battle history, siege states, regiment strength over time
- **Religions** — per-religion reform desire, tithe, saint power, member countries over time
- **Territory** — location and province snapshots
- **Demographics** — population by type, culture, religion, estate across time

## Tech Stack

- **Backend:** Python + FastAPI + watchdog
- **Storage:** SQLite (one database per game)
- **Frontend:** React + Vite + Recharts
- **Real-time:** WebSockets

## Project Documentation

See [`docs/`](docs/) for full architecture, design decisions, and game format documentation.

- [`docs/PROJECT.md`](docs/PROJECT.md) — Architecture and design decisions
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — Startup UI and watcher configuration
- [`docs/TOOLBOX.md`](docs/TOOLBOX.md) — Save file exploration scripts
- [`docs/games/eu5/`](docs/games/eu5/) — EU5 save format documentation

## Setup

### 1. Python environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Frontend

```bash
cd frontend
npm install
npm run build        # production build served by FastAPI
# or: npm run dev    # Vite dev server for hot-reload during development
```

### 3. Game data

See [`game-data/README.md`](game-data/README.md) for what to copy and where.

### 4. Running

One-click launch (recommended): double-click `start.bat` or run `start.ps1` from PowerShell. This activates the venv, installs missing deps, starts FastAPI + Vite, and opens the browser. `Ctrl+C` tears everything down.

Manual launch:

```bash
python run_server.py
```

The FastAPI app is `backend.api.app:create_app`. The server boots idle — open `http://localhost:8000` and start the pipeline from the **Config** tab.
