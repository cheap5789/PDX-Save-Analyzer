# PDX Save Analyzer

A live watcher and analyzer for Paradox grand strategy games.

Watches your save game directory, parses saves via [Rakaly](https://github.com/rakaly/cli), and streams live data to a configurable web dashboard — tracking country stats, time-series history, and key events (ruler deaths, wars, crises) suitable for After Action Reports.

## Status

🚧 Active development — EU5 (Europa Universalis V) is the first supported game.

## Features (planned)

- **Live file watcher** — detects new saves instantly via file system events
- **Multi-campaign support** — tracks SP and MP campaigns simultaneously, auto-detects campaign switches
- **Configurable snapshot frequency** — yearly, every 5 years, etc. to keep the database lean
- **Country stats dashboard** — gold, manpower, stability, prestige, income, population and more
- **Time-series charts** — track any metric across saves with trend lines
- **Event log** — ruler deaths, wars, crises, epidemics — auto-detected, annotatable for AAR writing
- **Multi-country comparison** — watch rivals, allies, and your own nation side by side

## Tech Stack

- **Backend:** Python + FastAPI + watchdog
- **Parser:** Rakaly CLI (binary → JSON)
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

*Coming soon — setup instructions will be added once the core pipeline is functional.*

## Rakaly

This project uses the [Rakaly CLI](https://github.com/rakaly/cli) to parse Paradox binary save files.
Place the appropriate binary for your platform in `bin/rakaly/`:
- `rakaly` (Linux x86_64)
- `rakaly.exe` (Windows x86_64)
