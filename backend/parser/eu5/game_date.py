"""
game_date.py — Paradox game date parsing and comparison

EU5 dates are strings like "1482.1.1" (year.month.day).
This module provides parsing, comparison, and snapshot frequency
threshold checks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class GameDate:
    """
    A Paradox game date (year.month.day).

    Comparable and sortable.  Month and day default to 1 if not provided.
    """
    year: int
    month: int = 1
    day: int = 1

    def __str__(self) -> str:
        return f"{self.year}.{self.month}.{self.day}"

    @classmethod
    def parse(cls, date_str: str) -> GameDate:
        """
        Parse a date string like "1482.1.1" or "1482".

        Tolerant of missing month/day (defaults to 1).
        """
        parts = date_str.strip().split(".")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return cls(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Snapshot frequency
# ---------------------------------------------------------------------------

# Maps frequency key -> year interval (0 = every save)
FREQUENCY_YEARS: dict[str, int] = {
    "every_save": 0,
    "yearly": 1,
    "5years": 5,
    "10years": 10,
    "25years": 25,
}

FREQUENCY_LABELS: dict[str, str] = {
    "every_save": "Every save",
    "yearly": "Every in-game year",
    "5years": "Every 5 years",
    "10years": "Every 10 years",
    "25years": "Every 25 years",
}


def should_snapshot(
    current_date: str | GameDate,
    last_snapshot_date: str | GameDate | None,
    frequency: str,
) -> bool:
    """
    Determine whether a snapshot should be recorded.

    Args:
        current_date:       The in-game date of the current save.
        last_snapshot_date:  The in-game date of the last recorded snapshot,
                             or None if no snapshots have been taken yet.
        frequency:           Frequency key (e.g. "yearly", "5years").

    Returns:
        True if a snapshot should be recorded.
    """
    # "every_save" always records
    interval = FREQUENCY_YEARS.get(frequency, 1)
    if interval == 0:
        return True

    # First snapshot always records
    if last_snapshot_date is None:
        return True

    # Parse dates
    if isinstance(current_date, str):
        current_date = GameDate.parse(current_date)
    if isinstance(last_snapshot_date, str):
        last_snapshot_date = GameDate.parse(last_snapshot_date)

    # Check if enough years have passed
    return (current_date.year - last_snapshot_date.year) >= interval
