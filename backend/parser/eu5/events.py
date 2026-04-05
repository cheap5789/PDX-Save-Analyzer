"""
events.py — Diff two GameSummary objects to produce typed events

Each event has a type, the game date it was detected at, and a payload dict
with event-specific data.  Events are stored in the `events` table regardless
of snapshot frequency.

Event types detected:
    Global:
        age_transition          — current_age changed
        situation_started       — a situation went from inactive → active/during
        situation_ended         — a situation went from active/during → after
        situation_changed       — any other status transition for a situation
    Country:
        ruler_changed           — player ruler name changed (AI rulers: future work)
        culture_changed         — primary_culture changed
        religion_changed        — primary_religion changed
        great_power_rank_changed — country enters or leaves the top-8 great powers
        capital_moved           — capital location ID changed
        country_appeared        — a country exists now that didn't before
        country_annexed         — a country that existed before is now gone
    War:
        war_started             — new war ID appeared
        war_ended               — war ID disappeared

GameEvent fields:
    event_type   — one of the event type strings above
    game_date    — in-game date string when the event was detected
    payload      — event-specific dict; always contains localised display names
                   alongside raw keys (e.g. situation_display, name_key, etc.)
    dedup_key    — stable unique string for one-time events (e.g. "war_start:42",
                   "sit_start:fall_of_delhi").  NULL for repeatable events.
                   Enforced as UNIQUE in the DB via a partial index — duplicate
                   inserts are silently dropped by INSERT OR IGNORE.
    country_tag  — TAG of the primary country for single-country events; NULL
                   for global and war events (wars carry participant lists in
                   payload.participants instead).

Payload keys by event type:
    age_transition:          from_age, from_age_display, to_age, to_age_display
    situation_started/ended: situation, situation_display, status/previous_status,
                             start_date/end_date
    situation_changed:       situation, situation_display, from_status, to_status
    ruler_changed:           tag, country, from_ruler, to_ruler
    culture_changed:         tag, country, from_culture, from_culture_key,
                             to_culture, to_culture_key
    religion_changed:        tag, country, from_religion, from_religion_key,
                             to_religion, to_religion_key
    great_power_rank_changed: tag, country, from_rank, to_rank
                             (only emitted when country crosses top-8 boundary)
    capital_moved:           tag, country, from_capital, to_capital
    country_appeared/annexed: tag, country
    war_started:             war_id, name, name_key, attackers, defenders,
                             participants (combined unique list)
    war_ended:               war_id, name, name_key, participants
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.parser.eu5.summary import GameSummary, CountrySummary, WarSummary


@dataclass
class GameEvent:
    """A single detected event."""
    event_type: str          # one of the types listed above
    game_date: str           # in-game date when detected (from the new save)
    payload: dict[str, Any]  # event-specific data
    dedup_key: str | None = None  # unique key for one-time events (prevents re-recording on restart)
    country_tag: str | None = None  # primary country tag for single-country events (None = global/war)

    def __repr__(self) -> str:
        return f"GameEvent({self.event_type!r}, {self.game_date}, {self.payload})"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Only emit great_power_rank_changed when a country crosses this boundary
# (i.e. enters rank ≤ GP_TOP_N or falls out of it).  Rank shuffles that stay
# entirely inside or entirely outside the top-N are not tracked.
GP_TOP_N = 8


# ---------------------------------------------------------------------------
# Main diff function
# ---------------------------------------------------------------------------

def diff_summaries(
    old: GameSummary | None,
    new: GameSummary,
) -> list[GameEvent]:
    """
    Compare two summaries and return a list of events.

    If old is None (first parse of a campaign), only structural events
    are emitted (e.g. initial war list).

    Args:
        old:  Previous summary (or None for first parse).
        new:  Current summary.

    Returns:
        List of GameEvent, in no particular order.
    """
    events: list[GameEvent] = []
    date = new.game_date

    if old is None:
        # First parse — no previous state to diff against.
        # Optionally emit initial state events here in the future.
        return events

    # --- Global events ---
    _diff_age(old, new, date, events)
    _diff_situations(old, new, date, events)

    # --- Country events ---
    _diff_countries(old, new, date, events)

    # --- War events ---
    _diff_wars(old, new, date, events)

    return events


# ---------------------------------------------------------------------------
# Internal diff functions
# ---------------------------------------------------------------------------

def _diff_age(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    if old.current_age != new.current_age:
        events.append(GameEvent(
            event_type="age_transition",
            game_date=date,
            payload={
                "from_age": old.current_age,
                "to_age": new.current_age,
                "from_age_display": old.current_age_display or old.current_age,
                "to_age_display": new.current_age_display or new.current_age,
            },
            dedup_key=f"age:{new.current_age}",
        ))


def _diff_situations(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    all_keys = set(old.situations) | set(new.situations)
    for key in all_keys:
        old_sit = old.situations.get(key)
        new_sit = new.situations.get(key)

        old_status = old_sit.status if old_sit else "inactive"
        new_status = new_sit.status if new_sit else "inactive"

        if old_status == new_status:
            continue

        # Resolve the best available display name for this situation
        sit_display = (
            (new_sit.display if new_sit and new_sit.display else None)
            or (old_sit.display if old_sit and old_sit.display else None)
            or key
        )

        # Situation started (inactive → anything active)
        if old_status == "inactive" and new_status != "inactive":
            events.append(GameEvent(
                event_type="situation_started",
                game_date=date,
                payload={
                    "situation": key,
                    "situation_display": sit_display,
                    "status": new_status,
                    "start_date": new_sit.start_date if new_sit else None,
                },
                dedup_key=f"sit_start:{key}",
            ))
        # Situation ended (active/during → after)
        elif new_status == "after" and old_status not in ("after", "inactive"):
            events.append(GameEvent(
                event_type="situation_ended",
                game_date=date,
                payload={
                    "situation": key,
                    "situation_display": sit_display,
                    "previous_status": old_status,
                    "end_date": new_sit.end_date if new_sit else None,
                },
                dedup_key=f"sit_end:{key}",
            ))
        # Any other status change
        elif old_status != new_status:
            events.append(GameEvent(
                event_type="situation_changed",
                game_date=date,
                payload={
                    "situation": key,
                    "situation_display": sit_display,
                    "from_status": old_status,
                    "to_status": new_status,
                },
            ))


def _diff_countries(
    old: GameSummary,
    new: GameSummary,
    date: str,
    events: list[GameEvent],
) -> None:
    all_tags = set(old.countries) | set(new.countries)

    for tag in all_tags:
        old_c = old.countries.get(tag)
        new_c = new.countries.get(tag)

        # Country appeared
        if old_c is None and new_c is not None:
            events.append(GameEvent(
                event_type="country_appeared",
                game_date=date,
                payload={"tag": tag, "country": new_c.country_display or tag},
                country_tag=tag,
            ))
            continue

        # Country annexed / disappeared
        if old_c is not None and new_c is None:
            events.append(GameEvent(
                event_type="country_annexed",
                game_date=date,
                payload={"tag": tag, "country": old_c.country_display or tag},
                country_tag=tag,
            ))
            continue

        # Both exist — check fields
        assert old_c is not None and new_c is not None

        # Ruler change (player only — AI rulers TBD)
        if old_c.ruler_name and new_c.ruler_name and old_c.ruler_name != new_c.ruler_name:
            events.append(GameEvent(
                event_type="ruler_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_ruler": old_c.ruler_name,
                    "to_ruler": new_c.ruler_name,
                },
                country_tag=tag,
            ))

        # Culture change
        if old_c.primary_culture != new_c.primary_culture:
            events.append(GameEvent(
                event_type="culture_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_culture": old_c.culture_display or old_c.primary_culture,
                    "to_culture": new_c.culture_display or new_c.primary_culture,
                    "from_culture_key": old_c.primary_culture,
                    "to_culture_key": new_c.primary_culture,
                },
                country_tag=tag,
            ))

        # Religion change
        if old_c.primary_religion != new_c.primary_religion:
            events.append(GameEvent(
                event_type="religion_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_religion": old_c.religion_display or old_c.primary_religion,
                    "to_religion": new_c.religion_display or new_c.primary_religion,
                    "from_religion_key": old_c.primary_religion,
                    "to_religion_key": new_c.primary_religion,
                },
                country_tag=tag,
            ))

        # Rank change — only emit when a country crosses the top-8 boundary
        # (enters or leaves the great-power top tier).  Shuffles within or
        # outside the top tier are not tracked.
        old_rank = old_c.great_power_rank
        new_rank = new_c.great_power_rank
        old_in_top = 0 < old_rank <= GP_TOP_N
        new_in_top = 0 < new_rank <= GP_TOP_N
        if old_in_top != new_in_top:
            events.append(GameEvent(
                event_type="great_power_rank_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_rank": old_rank,
                    "to_rank": new_rank,
                },
                country_tag=tag,
            ))

        # Capital moved
        if old_c.capital != new_c.capital:
            events.append(GameEvent(
                event_type="capital_moved",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_capital": old_c.capital,
                    "to_capital": new_c.capital,
                },
                country_tag=tag,
            ))


def _diff_wars(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    old_ids = set(old.wars)
    new_ids = set(new.wars)

    # New wars
    for wid in new_ids - old_ids:
        war = new.wars[wid]
        attackers = war.attackers or []
        defenders = war.defenders or []
        # Combined participant list (unique tags, order: attackers first)
        seen: set[str] = set()
        participants: list[str] = []
        for tag in attackers + defenders:
            if tag and tag not in seen:
                participants.append(tag)
                seen.add(tag)
        events.append(GameEvent(
            event_type="war_started",
            game_date=date,
            payload={
                "war_id": wid,
                "name": war.name_display or war.name,
                "name_key": war.name,
                "attackers": attackers,
                "defenders": defenders,
                "participants": participants,
            },
            dedup_key=f"war_start:{wid}",
        ))

    # Ended wars
    for wid in old_ids - new_ids:
        war = old.wars[wid]
        attackers = war.attackers or []
        defenders = war.defenders or []
        seen = set()
        participants = []
        for tag in attackers + defenders:
            if tag and tag not in seen:
                participants.append(tag)
                seen.add(tag)
        events.append(GameEvent(
            event_type="war_ended",
            game_date=date,
            payload={
                "war_id": wid,
                "name": war.name_display or war.name,
                "name_key": war.name,
                "participants": participants,
            },
            dedup_key=f"war_end:{wid}",
        ))
