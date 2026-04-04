#!/usr/bin/env python3
"""
run_watcher.py — Standalone runner for the watcher pipeline

Development / testing entry point.  Runs the full pipeline
(file watcher → parser → snapshot/events → SQLite) from the command line.

Usage:
    python run_watcher.py --save-dir "C:/Users/PH/Documents/Paradox Interactive/Europa Universalis V/save games" \
                          --install-path "C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis V" \
                          --freq yearly

    # Minimal (uses defaults):
    python run_watcher.py --save-dir <path> --install-path <path>

Press Ctrl+C to stop.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.config import SessionConfig
from backend.watcher.pipeline import WatcherPipeline
from backend.parser.eu5.events import GameEvent


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _on_snapshot(data: dict) -> None:
    """Callback: a snapshot was recorded."""
    countries = data.get("countries", {})
    date = data.get("game_date", "?")
    print(f"\n  📊 Snapshot at {date} — {len(countries)} countries tracked")
    for tag, fields in list(countries.items())[:5]:
        gold = fields.get("gold", "?")
        print(f"     {tag}: gold={gold}")


def _on_events(events: list[GameEvent]) -> None:
    """Callback: events were detected."""
    for e in events:
        emoji = {
            "age_transition": "🌅",
            "ruler_changed": "👑",
            "war_started": "⚔️",
            "war_ended": "🕊️",
            "country_annexed": "💀",
            "country_appeared": "🏰",
            "culture_changed": "🎭",
            "religion_changed": "⛪",
            "situation_started": "⚡",
            "situation_ended": "✅",
            "great_power_rank_changed": "📈",
            "capital_moved": "🏛️",
        }.get(e.event_type, "📝")
        print(f"  {emoji} [{e.game_date}] {e.event_type}: {e.payload}")


def _on_switch(old_id: str, new_id: str) -> None:
    """Callback: playthrough switched."""
    print(f"\n  🔄 Playthrough switch: {old_id[:8]}... → {new_id[:8]}...")


async def run(config: SessionConfig) -> None:
    pipeline = WatcherPipeline(
        config,
        on_snapshot=_on_snapshot,
        on_events=_on_events,
        on_playthrough_switch=_on_switch,
    )

    print(f"\n{'='*60}")
    print(f"  PDX Save Analyzer — Watcher")
    print(f"{'='*60}")
    print(f"  Game         : {config.game}")
    print(f"  Save dir     : {config.save_directory}")
    print(f"  Install path : {config.game_install_path}")
    print(f"  Language     : {config.language}")
    print(f"  Frequency    : {config.snapshot_freq}")
    print(f"  Database     : {config.db_path}")
    print(f"  Rakaly       : {config.rakaly_bin}")
    print(f"{'='*60}")
    print(f"  Watching for .eu5 files... (Ctrl+C to stop)\n")

    await pipeline.start()

    try:
        # Run until interrupted
        while pipeline.is_running:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await pipeline.stop()
        print("\nWatcher stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="PDX Save Analyzer — Watcher")
    parser.add_argument("--save-dir", required=True, help="Save game directory to watch")
    parser.add_argument("--install-path", required=True, help="Game install path")
    parser.add_argument("--game", default="eu5", help="Game ID (default: eu5)")
    parser.add_argument("--freq", default="yearly",
                        choices=["every_save", "yearly", "5years", "10years", "25years"],
                        help="Snapshot frequency (default: yearly)")
    parser.add_argument("--language", default="english", help="Localisation language")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = SessionConfig(
        game=args.game,
        game_install_path=Path(args.install_path),
        save_directory=Path(args.save_dir),
        snapshot_freq=args.freq,
        language=args.language,
    )

    # Validate paths
    if not config.save_directory.exists():
        print(f"Error: Save directory not found: {config.save_directory}")
        sys.exit(1)
    if not config.rakaly_bin.exists():
        print(f"Error: Rakaly binary not found: {config.rakaly_bin}")
        print(f"  Expected at: {config.rakaly_bin.resolve()}")
        sys.exit(1)

    asyncio.run(run(config))


if __name__ == "__main__":
    main()
