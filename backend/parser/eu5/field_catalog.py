"""
field_catalog.py — Curated registry of trackable EU5 country fields

Each FieldDef describes one numeric value that can be extracted from a
country object in the save JSON.  The user toggles fields on/off per
campaign; only enabled fields are recorded in snapshot rows.

Path templates use {cid} for the country's numeric ID in the JSON.
The snapshot extractor resolves these at runtime.

Categories help the UI group fields into sections.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDef:
    key: str                 # unique identifier (e.g. "gold")
    display_name: str        # human label shown in UI
    json_path: str           # dot-path inside country object (relative to countries.database.{cid})
    value_type: str          # "float", "int", "str"
    category: str            # grouping: economy, military, diplomacy, score, demographics, religion
    default_enabled: bool    # whether it's on by default for new campaigns
    description: str = ""    # tooltip / help text


# ---------------------------------------------------------------------------
# The catalog.
#
# Organised by category.  json_path is relative to a country object
# (i.e. countries.database[cid]).
# ---------------------------------------------------------------------------

FIELD_CATALOG: list[FieldDef] = [
    # ── Economy ───────────────────────────────────────────────────────────
    FieldDef(
        key="gold",
        display_name="Treasury",
        json_path="currency_data.gold",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Current gold in the treasury",
    ),
    FieldDef(
        key="gold_monthly",
        display_name="Monthly Gold",
        json_path="balance_history_2.Gold",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Monthly gold income delta",
    ),
    FieldDef(
        key="estimated_monthly_income",
        display_name="Est. Monthly Income",
        json_path="estimated_monthly_income",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Total estimated monthly income",
    ),
    FieldDef(
        key="estimated_monthly_income_trade_and_tax",
        display_name="Trade+Tax Income",
        json_path="estimated_monthly_income_trade_and_tax",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_month_gold_income",
        display_name="Last Month Income",
        json_path="last_month_gold_income",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="inflation",
        display_name="Inflation",
        json_path="currency_data.inflation",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="inflation_monthly",
        display_name="Monthly Inflation",
        json_path="balance_history_2.Inflation",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="current_tax_base",
        display_name="Tax Base",
        json_path="current_tax_base",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="potential_tax_base",
        display_name="Potential Tax Base",
        json_path="potential_tax_base",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="monthly_trade_value",
        display_name="Monthly Trade Value",
        json_path="monthly_trade_value",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="monthly_trade_balance",
        display_name="Monthly Trade Balance",
        json_path="monthly_trade_balance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="total_produced",
        display_name="Total Goods Produced",
        json_path="total_produced",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_months_tax_income",
        display_name="Last Month Tax",
        json_path="last_months_tax_income",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_months_army_maintenance",
        display_name="Army Maintenance",
        json_path="last_months_army_maintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_months_fort_maintenance",
        display_name="Fort Maintenance",
        json_path="last_months_fort_maintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_months_building_maintenance",
        display_name="Building Maintenance",
        json_path="last_months_building_maintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),

    # ── Military ──────────────────────────────────────────────────────────
    FieldDef(
        key="manpower",
        display_name="Manpower",
        json_path="currency_data.manpower",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="manpower_monthly",
        display_name="Monthly Manpower",
        json_path="balance_history_2.Manpower",
        value_type="float",
        category="military",
        default_enabled=False,
    ),
    FieldDef(
        key="max_manpower",
        display_name="Max Manpower",
        json_path="max_manpower",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="monthly_manpower",
        display_name="Manpower Recovery",
        json_path="monthly_manpower",
        value_type="float",
        category="military",
        default_enabled=False,
    ),
    FieldDef(
        key="army_tradition",
        display_name="Army Tradition",
        json_path="currency_data.army_tradition",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="army_tradition_monthly",
        display_name="Monthly Army Tradition",
        json_path="balance_history_2.ArmyTradition",
        value_type="float",
        category="military",
        default_enabled=False,
    ),
    FieldDef(
        key="war_exhaustion",
        display_name="War Exhaustion",
        json_path="balance_history_2.WarExhaustion",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Monthly war exhaustion change",
    ),

    # ── Stability & Government ────────────────────────────────────────────
    FieldDef(
        key="stability",
        display_name="Stability",
        json_path="currency_data.stability",
        value_type="float",
        category="stability",
        default_enabled=True,
    ),
    FieldDef(
        key="stability_monthly",
        display_name="Monthly Stability",
        json_path="balance_history_2.Stability",
        value_type="float",
        category="stability",
        default_enabled=False,
    ),
    FieldDef(
        key="government_power",
        display_name="Government Power",
        json_path="currency_data.government_power",
        value_type="float",
        category="stability",
        default_enabled=True,
    ),
    FieldDef(
        key="government_power_monthly",
        display_name="Monthly Gov. Power",
        json_path="balance_history_2.GovernmentPower",
        value_type="float",
        category="stability",
        default_enabled=False,
    ),
    FieldDef(
        key="complacency_monthly",
        display_name="Monthly Complacency",
        json_path="balance_history_2.Complacency",
        value_type="float",
        category="stability",
        default_enabled=False,
    ),

    # ── Prestige & Diplomacy ──────────────────────────────────────────────
    FieldDef(
        key="prestige",
        display_name="Prestige",
        json_path="currency_data.prestige",
        value_type="float",
        category="diplomacy",
        default_enabled=True,
    ),
    FieldDef(
        key="prestige_monthly",
        display_name="Monthly Prestige",
        json_path="balance_history_2.Prestige",
        value_type="float",
        category="diplomacy",
        default_enabled=False,
    ),

    # ── Religion ──────────────────────────────────────────────────────────
    FieldDef(
        key="religious_influence",
        display_name="Religious Influence",
        json_path="currency_data.religious_influence",
        value_type="float",
        category="religion",
        default_enabled=False,
    ),
    FieldDef(
        key="religious_influence_monthly",
        display_name="Monthly Relig. Influence",
        json_path="balance_history_2.ReligiousInfluence",
        value_type="float",
        category="religion",
        default_enabled=False,
    ),
    FieldDef(
        key="karma",
        display_name="Karma",
        json_path="currency_data.karma",
        value_type="float",
        category="religion",
        default_enabled=False,
        description="Religion-specific mechanic (unverified which religions use it)",
    ),
    FieldDef(
        key="purity",
        display_name="Purity",
        json_path="currency_data.purity",
        value_type="float",
        category="religion",
        default_enabled=False,
    ),
    FieldDef(
        key="righteousness",
        display_name="Righteousness",
        json_path="currency_data.righteousness",
        value_type="float",
        category="religion",
        default_enabled=False,
    ),

    # ── Score & Rank ──────────────────────────────────────────────────────
    FieldDef(
        key="great_power_rank",
        display_name="Great Power Rank",
        json_path="great_power_rank",
        value_type="int",
        category="score",
        default_enabled=True,
    ),
    FieldDef(
        key="score_place",
        display_name="Overall Score Rank",
        json_path="score.score_place",
        value_type="int",
        category="score",
        default_enabled=True,
    ),
    FieldDef(
        key="score_adm",
        display_name="ADM Score",
        json_path="score.score_rating.ADM",
        value_type="float",
        category="score",
        default_enabled=False,
    ),
    FieldDef(
        key="score_dip",
        display_name="DIP Score",
        json_path="score.score_rating.DIP",
        value_type="float",
        category="score",
        default_enabled=False,
    ),
    FieldDef(
        key="score_mil",
        display_name="MIL Score",
        json_path="score.score_rating.MIL",
        value_type="float",
        category="score",
        default_enabled=False,
    ),

    # ── Demographics ──────────────────────────────────────────────────────
    FieldDef(
        key="population",
        display_name="Population",
        json_path="last_months_population",
        value_type="float",
        category="demographics",
        default_enabled=True,
    ),

    # ── Technology ────────────────────────────────────────────────────────
    FieldDef(
        key="starting_technology_level",
        display_name="Starting Tech Level",
        json_path="starting_technology_level",
        value_type="int",
        category="technology",
        default_enabled=False,
        description="Starting tech level (static — may not change during game)",
    ),
    FieldDef(
        key="naval_range",
        display_name="Naval Range",
        json_path="naval_range",
        value_type="float",
        category="technology",
        default_enabled=False,
    ),
    FieldDef(
        key="colonial_range",
        display_name="Colonial Range",
        json_path="colonial_range",
        value_type="float",
        category="technology",
        default_enabled=False,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fast lookup by key
_CATALOG_MAP: dict[str, FieldDef] = {f.key: f for f in FIELD_CATALOG}


def get_field(key: str) -> FieldDef | None:
    """Look up a field definition by its unique key."""
    return _CATALOG_MAP.get(key)


def get_default_fields() -> list[FieldDef]:
    """Return all fields that are enabled by default."""
    return [f for f in FIELD_CATALOG if f.default_enabled]


def get_fields_by_category(category: str) -> list[FieldDef]:
    """Return all fields in a given category."""
    return [f for f in FIELD_CATALOG if f.category == category]


def all_categories() -> list[str]:
    """Return the list of distinct categories, in catalog order."""
    seen: set[str] = set()
    result: list[str] = []
    for f in FIELD_CATALOG:
        if f.category not in seen:
            seen.add(f.category)
            result.append(f.category)
    return result


def resolve_field_value(country_obj: dict, field: FieldDef) -> float | int | str | None:
    """
    Extract a field's value from a country object by following its json_path.

    Returns None if the path doesn't exist (field absent from this country).
    """
    node = country_obj
    for part in field.json_path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    # Type coercion
    if field.value_type == "float":
        try:
            return float(node)
        except (TypeError, ValueError):
            return None
    if field.value_type == "int":
        try:
            return int(node)
        except (TypeError, ValueError):
            return None
    return node
