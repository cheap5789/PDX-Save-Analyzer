"""
config.py — Session configuration dataclass

Holds all the runtime configuration for a watcher session.
This is populated from the startup UI (Phase 5) or from command-line
arguments during development.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionConfig:
    """Runtime configuration for one watcher session."""

    # Required — provided by user
    game: str                       # "eu5" (only supported game for now)
    game_install_path: Path         # Root EU5 install directory
    save_directory: Path            # Where the game writes .eu5 saves
    snapshot_freq: str = "yearly"   # Frequency key: "every_save", "yearly", "5years", etc.
    language: str = "english"       # Localisation language subfolder name

    # Derived from install path
    @property
    def loc_dir(self) -> Path:
        """Full path to localisation .yml files."""
        return self.game_install_path / "game" / "main_menu" / "localization" / self.language

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file for this game."""
        return Path("data") / f"{self.game}.db"

    @property
    def rakaly_bin(self) -> Path:
        """Path to the rakaly CLI binary."""
        return Path("bin/rakaly/rakaly")

    # Optional — auto-detected from first save
    country_tag: str = ""
    country_name: str = ""
    playthrough_id: str = ""
    multiplayer: bool = False
    game_version: str = ""

    # Field selection
    enabled_field_keys: list[str] = field(default_factory=list)

    def save_extensions(self) -> list[str]:
        """File extensions to watch for this game."""
        extensions: dict[str, list[str]] = {
            "eu5": [".eu5"],
            "ck3": [".ck3"],
            "hoi4": [".hoi4"],
            "vic3": [".v3"],
            "imperator": [".rome"],
        }
        return extensions.get(self.game, [f".{self.game}"])
