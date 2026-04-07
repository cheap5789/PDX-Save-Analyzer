"""
field_catalog.py — Curated registry of trackable EU5 country fields

Each FieldDef describes one numeric value that can be extracted from a
country object in the save JSON.  The user toggles fields on/off per
campaign; only enabled fields are recorded in snapshot rows.

Path resolution:
  - Default paths are relative to countries.database.{cid}
    e.g. "currency_data.gold" → countries.database[cid].currency_data.gold
  - Paths starting with "@diplomacy:" are relative to diplomacy_manager.{cid}
    e.g. "@diplomacy:diplomats" → diplomacy_manager[cid].diplomats
  - Paths starting with "@ruler:" resolve through character_db.database
    using government.ruler as the character ID
    e.g. "@ruler:adm" → character_db.database[government.ruler].adm
  - Paths starting with "@heir:" same but via government.heir

Categories help the UI group fields into sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldDef:
    key: str                 # unique identifier (e.g. "gold")
    display_name: str        # human label shown in UI
    json_path: str           # dot-path (see resolution rules above)
    value_type: str          # "float", "int", "str", "json"
    category: str            # grouping: economy, military, diplomacy, score, demographics, religion, etc.
    default_enabled: bool    # whether it's on by default for new campaigns
    description: str = ""    # tooltip / help text
    display_format: str = "" # formatting hint for the UI:
                             #   "x1000"  — multiply raw value by 1000, show as integer with locale separators
                             #   "percent" — value is already on a 0–100 (or −100–+100) scale, append %
                             #   ""        — plain number (2 decimal places)


# ---------------------------------------------------------------------------
# The catalog.
#
# Organised by category.  json_path is relative to a country object
# (i.e. countries.database[cid]) unless prefixed with @diplomacy:, @ruler:, @heir:.
# ---------------------------------------------------------------------------

FIELD_CATALOG: list[FieldDef] = [

    # ── Economy — Currency Data ──────────────────────────────────────────
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
        description="Monthly gold income delta (actual treasury change incl. one-offs)",
    ),
    FieldDef(
        key="inflation",
        display_name="Inflation",
        json_path="currency_data.inflation",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Inflation level (raw, ×100 for display)",
    ),
    FieldDef(
        key="inflation_monthly",
        display_name="Monthly Inflation",
        json_path="balance_history_2.Inflation",
        value_type="float",
        category="economy",
        default_enabled=True,
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
        default_enabled=True,
    ),
    FieldDef(
        key="last_month_gold_income",
        display_name="Last Month Income",
        json_path="last_month_gold_income",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="current_tax_base",
        display_name="Tax Base",
        json_path="current_tax_base",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="potential_tax_base",
        display_name="Potential Tax Base",
        json_path="potential_tax_base",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="monthly_trade_value",
        display_name="Monthly Trade Value",
        json_path="monthly_trade_value",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="monthly_trade_balance",
        display_name="Monthly Trade Balance",
        json_path="monthly_trade_balance",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="total_produced",
        display_name="Total Goods Produced",
        json_path="total_produced",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="last_months_tax_income",
        display_name="Last Month Tax",
        json_path="last_months_tax_income",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),

    # ── Economy — Maintenance ────────────────────────────────────────────
    FieldDef(
        key="last_months_army_maintenance",
        display_name="Army Maintenance",
        json_path="last_months_army_maintenance",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="last_months_navy_maintenance",
        display_name="Navy Maintenance",
        json_path="last_months_navy_maintenance",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="last_months_fort_maintenance",
        display_name="Fort Maintenance",
        json_path="last_months_fort_maintenance",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="last_months_building_maintenance",
        display_name="Building Maintenance",
        json_path="last_months_building_maintenance",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),

    # ── Economy — Maintenance Sliders ────────────────────────────────────
    FieldDef(
        key="court_maintenance_slider",
        display_name="Court Maintenance Slider",
        json_path="economy.maintenances.CourtMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
        description="Court spending slider 0–1. Absent = no court mechanic.",
    ),
    FieldDef(
        key="army_maintenance_slider",
        display_name="Army Maint. Slider",
        json_path="economy.maintenances.ArmyMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="navy_maintenance_slider",
        display_name="Navy Maint. Slider",
        json_path="economy.maintenances.NavyMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="fort_maintenance_slider",
        display_name="Fort Maint. Slider",
        json_path="economy.maintenances.FortMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="food_maintenance_slider",
        display_name="Food Maint. Slider",
        json_path="economy.maintenances.FoodMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),
    FieldDef(
        key="upkeep_maintenance_slider",
        display_name="Upkeep Maint. Slider",
        json_path="economy.maintenances.UpkeepMaintenance",
        value_type="float",
        category="economy",
        default_enabled=False,
    ),

    # ── Economy — Aggregate & Historical ─────────────────────────────────
    FieldDef(
        key="economy_income",
        display_name="Monthly Income (current)",
        json_path="economy.income",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Current month total income (aggregate, no per-category breakdown)",
    ),
    FieldDef(
        key="economy_expense",
        display_name="Monthly Expense (current)",
        json_path="economy.expense",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Current month total expenses (aggregate)",
    ),
    FieldDef(
        key="economy_balance",
        display_name="Monthly Net Balance",
        json_path="economy.recent_balance.-1",
        value_type="float",
        category="economy",
        default_enabled=True,
        description="Last entry of economy.recent_balance rolling 12-month array (income − expense)",
    ),
    FieldDef(
        key="total_debt",
        display_name="Total Debt",
        json_path="economy.total_debt",
        value_type="float",
        category="economy",
        default_enabled=True,
    ),
    FieldDef(
        key="historical_tax_base",
        display_name="Historical Tax Base",
        json_path="historical_tax_base",
        value_type="json",
        category="economy",
        default_enabled=False,
        description="Yearly snapshots from game start (flat array of floats, index = year offset)",
    ),
    FieldDef(
        key="historical_population",
        display_name="Historical Population",
        json_path="historical_population",
        value_type="json",
        category="economy",
        default_enabled=False,
        description="Yearly snapshots from game start (flat array of floats, pop-mass unit)",
    ),
    FieldDef(
        key="last_month_produced",
        display_name="Goods Produced (breakdown)",
        json_path="last_month_produced",
        value_type="json",
        category="economy",
        default_enabled=False,
        description="Dict of good_key → amount. total_produced = sum of values.",
    ),

    # ── Military ──────────────────────────────────────────────────────────
    FieldDef(
        key="manpower",
        display_name="Manpower",
        json_path="currency_data.manpower",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Current manpower (raw save value; ×1000 = display value)",
        display_format="x1000",
    ),
    FieldDef(
        key="manpower_monthly",
        display_name="Monthly Manpower",
        json_path="balance_history_2.Manpower",
        value_type="float",
        category="military",
        default_enabled=True,
        display_format="x1000",
    ),
    FieldDef(
        key="max_manpower",
        display_name="Max Manpower",
        json_path="max_manpower",
        value_type="float",
        category="military",
        default_enabled=True,
        display_format="x1000",
    ),
    FieldDef(
        key="monthly_manpower",
        display_name="Manpower Recovery",
        json_path="monthly_manpower",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Monthly manpower gain (raw save value; ×1000 = display value)",
        display_format="x1000",
    ),
    FieldDef(
        key="sailors",
        display_name="Sailors",
        json_path="currency_data.sailors",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Current sailors (raw save value; ×1000 = display value)",
        display_format="x1000",
    ),
    FieldDef(
        key="sailors_monthly",
        display_name="Monthly Sailors",
        json_path="balance_history_2.Sailors",
        value_type="float",
        category="military",
        default_enabled=True,
        display_format="x1000",
    ),
    FieldDef(
        key="max_sailors",
        display_name="Max Sailors",
        json_path="max_sailors",
        value_type="float",
        category="military",
        default_enabled=True,
        display_format="x1000",
    ),
    FieldDef(
        key="monthly_sailors",
        display_name="Sailor Recovery",
        json_path="monthly_sailors",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Monthly sailor gain (raw save value; ×1000 = display value)",
        display_format="x1000",
    ),
    FieldDef(
        key="this_months_manpower_losses",
        display_name="Monthly Manpower Losses",
        json_path="this_months_manpower_losses",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Losses this month (raw save value; ×1000 = display value; negative = losses)",
        display_format="x1000",
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
        default_enabled=True,
    ),
    FieldDef(
        key="navy_tradition",
        display_name="Navy Tradition",
        json_path="currency_data.navy_tradition",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="navy_tradition_monthly",
        display_name="Monthly Navy Tradition",
        json_path="balance_history_2.NavyTradition",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="war_exhaustion",
        display_name="War Exhaustion",
        json_path="currency_data.war_exhaustion",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="war_exhaustion_monthly",
        display_name="Monthly War Exhaustion",
        json_path="balance_history_2.WarExhaustion",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="expected_army_size",
        display_name="Expected Army Size",
        json_path="expected_army_size",
        value_type="float",
        category="military",
        default_enabled=True,
        description="Indicative army size (useful for tracking military buildup)",
    ),
    FieldDef(
        key="expected_navy_size",
        display_name="Expected Navy Size",
        json_path="expected_navy_size",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="naval_range",
        display_name="Naval Range",
        json_path="naval_range",
        value_type="float",
        category="military",
        default_enabled=True,
    ),
    FieldDef(
        key="colonial_range",
        display_name="Colonial Range",
        json_path="colonial_range",
        value_type="float",
        category="military",
        default_enabled=True,
    ),

    # ── Stability & Government ────────────────────────────────────────────
    FieldDef(
        key="stability",
        display_name="Stability",
        json_path="currency_data.stability",
        value_type="float",
        category="stability",
        default_enabled=True,
        description="−100 to +100 scale (displayed as %)",
        display_format="percent",
    ),
    FieldDef(
        key="stability_monthly",
        display_name="Monthly Stability",
        json_path="balance_history_2.Stability",
        value_type="float",
        category="stability",
        default_enabled=True,
    ),
    FieldDef(
        key="government_power",
        display_name="Government Power",
        json_path="currency_data.government_power",
        value_type="float",
        category="stability",
        default_enabled=True,
        description="0–100 scale",
    ),
    FieldDef(
        key="government_power_monthly",
        display_name="Monthly Gov. Power",
        json_path="balance_history_2.GovernmentPower",
        value_type="float",
        category="stability",
        default_enabled=True,
    ),
    FieldDef(
        key="complacency",
        display_name="Complacency",
        json_path="currency_data.complacency",
        value_type="float",
        category="stability",
        default_enabled=True,
        description="Complacency stock (critical threshold at 90)",
    ),
    FieldDef(
        key="complacency_monthly",
        display_name="Monthly Complacency",
        json_path="balance_history_2.Complacency",
        value_type="float",
        category="stability",
        default_enabled=True,
    ),

    # ── Government — Structure ───────────────────────────────────────────
    FieldDef(
        key="level",
        display_name="Country Level",
        json_path="level",
        value_type="int",
        category="government",
        default_enabled=True,
        description="Country level (absent = 1). Level-up is a rank event.",
    ),
    FieldDef(
        key="government_type",
        display_name="Government Type",
        json_path="government.type",
        value_type="str",
        category="government",
        default_enabled=True,
        description="E.g. monarchy, republic, theocracy. Change = governance event.",
    ),
    FieldDef(
        key="heir_selection",
        display_name="Succession Law",
        json_path="government.heir_selection",
        value_type="str",
        category="government",
        default_enabled=True,
        description="E.g. cognatic_primogeniture. Change = succession law event.",
    ),
    FieldDef(
        key="parliament_type",
        display_name="Parliament Type",
        json_path="government.parliament.parliament_type",
        value_type="str",
        category="government",
        default_enabled=True,
        description="E.g. estate_parliament. Significant governance milestone.",
    ),

    # ── Government — Ruler & Heir ────────────────────────────────────────
    FieldDef(
        key="ruler_adm",
        display_name="Ruler ADM",
        json_path="@ruler:adm",
        value_type="float",
        category="government",
        default_enabled=True,
        description="Ruler administrative skill. Resolved via character_db.",
    ),
    FieldDef(
        key="ruler_dip",
        display_name="Ruler DIP",
        json_path="@ruler:dip",
        value_type="float",
        category="government",
        default_enabled=True,
    ),
    FieldDef(
        key="ruler_mil",
        display_name="Ruler MIL",
        json_path="@ruler:mil",
        value_type="float",
        category="government",
        default_enabled=True,
    ),
    FieldDef(
        key="ruler_name",
        display_name="Ruler Name",
        json_path="@ruler:first_name",
        value_type="str",
        category="government",
        default_enabled=True,
        description="Name key of the ruler (localised at display time).",
    ),
    FieldDef(
        key="heir_adm",
        display_name="Heir ADM",
        json_path="@heir:adm",
        value_type="float",
        category="government",
        default_enabled=False,
    ),
    FieldDef(
        key="heir_dip",
        display_name="Heir DIP",
        json_path="@heir:dip",
        value_type="float",
        category="government",
        default_enabled=False,
    ),
    FieldDef(
        key="heir_mil",
        display_name="Heir MIL",
        json_path="@heir:mil",
        value_type="float",
        category="government",
        default_enabled=False,
    ),
    FieldDef(
        key="heir_name",
        display_name="Heir Name",
        json_path="@heir:first_name",
        value_type="str",
        category="government",
        default_enabled=False,
    ),

    # ── Government — Societal Values (16 sliders) ────────────────────────
    FieldDef(
        key="sv_centralization",
        display_name="Centralization",
        json_path="government.societal_values.centralization_vs_decentralization",
        value_type="float",
        category="societal_values",
        default_enabled=True,
        description="Societal values slider. -999 = N/A for this country.",
    ),
    FieldDef(
        key="sv_traditionalist",
        display_name="Traditionalist vs Innovative",
        json_path="government.societal_values.traditionalist_vs_innovative",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_spiritualist",
        display_name="Spiritualist vs Humanist",
        json_path="government.societal_values.spiritualist_vs_humanist",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_aristocracy",
        display_name="Aristocracy vs Plutocracy",
        json_path="government.societal_values.aristocracy_vs_plutocracy",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_serfdom",
        display_name="Serfdom vs Free Subjects",
        json_path="government.societal_values.serfdom_vs_free_subjects",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_mercantilism",
        display_name="Mercantilism vs Free Trade",
        json_path="government.societal_values.mercantilism_vs_free_trade",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_belligerent",
        display_name="Belligerent vs Conciliatory",
        json_path="government.societal_values.belligerent_vs_conciliatory",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_quality",
        display_name="Quality vs Quantity",
        json_path="government.societal_values.quality_vs_quantity",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_offensive",
        display_name="Offensive vs Defensive",
        json_path="government.societal_values.offensive_vs_defensive",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_land",
        display_name="Land vs Naval",
        json_path="government.societal_values.land_vs_naval",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_capital_economy",
        display_name="Capital vs Traditional Economy",
        json_path="government.societal_values.capital_economy_vs_traditional_economy",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_individualism",
        display_name="Individualism vs Communalism",
        json_path="government.societal_values.individualism_vs_communalism",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_outward",
        display_name="Outward vs Inward",
        json_path="government.societal_values.outward_vs_inward",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_sinicized",
        display_name="Sinicized vs Unsinicized",
        json_path="government.societal_values.sinicized_vs_unsinicized",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_absolutism",
        display_name="Absolutism vs Liberalism",
        json_path="government.societal_values.absolutism_vs_liberalism",
        value_type="float",
        category="societal_values",
        default_enabled=True,
    ),
    FieldDef(
        key="sv_mysticism",
        display_name="Mysticism vs Jurisprudence",
        json_path="government.societal_values.mysticism_vs_jurisprudence",
        value_type="float",
        category="societal_values",
        default_enabled=True,
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
        default_enabled=True,
    ),
    FieldDef(
        key="diplomats",
        display_name="Diplomats",
        json_path="@diplomacy:diplomats",
        value_type="float",
        category="diplomacy",
        default_enabled=True,
        description="Current diplomat pool. Stored in diplomacy_manager[cid].",
    ),
    FieldDef(
        key="threat",
        display_name="Threat",
        json_path="@diplomacy:threat",
        value_type="float",
        category="diplomacy",
        default_enabled=True,
        description="Aggressive expansion / threat level.",
    ),
    FieldDef(
        key="rival_count",
        display_name="Rival Count",
        json_path="@diplomacy:rivals_2.list",
        value_type="list_len",
        category="diplomacy",
        default_enabled=True,
        description="Number of rivals. Derived from length of rivals_2.list.",
    ),
    FieldDef(
        key="enemy_count",
        display_name="Enemy Count",
        json_path="@diplomacy:enemy",
        value_type="int",
        category="diplomacy",
        default_enabled=True,
        description="Number of enemies.",
    ),
    FieldDef(
        key="last_war",
        display_name="Last War Date",
        json_path="@diplomacy:last_war",
        value_type="str",
        category="diplomacy",
        default_enabled=False,
    ),
    FieldDef(
        key="last_peace",
        display_name="Last Peace Date",
        json_path="@diplomacy:last_peace",
        value_type="str",
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
        default_enabled=True,
    ),
    FieldDef(
        key="religious_influence_monthly",
        display_name="Monthly Relig. Influence",
        json_path="balance_history_2.ReligiousInfluence",
        value_type="float",
        category="religion",
        default_enabled=True,
    ),
    FieldDef(
        key="karma",
        display_name="Karma",
        json_path="currency_data.karma",
        value_type="float",
        category="religion",
        default_enabled=True,
        description="Buddhist religion mechanic (bon, mahayana, theravada, sammitiya, tibetan_buddhism)",
    ),
    FieldDef(
        key="purity",
        display_name="Purity",
        json_path="currency_data.purity",
        value_type="float",
        category="religion",
        default_enabled=True,
        description="Shinto religion mechanic",
    ),
    FieldDef(
        key="righteousness",
        display_name="Righteousness",
        json_path="currency_data.righteousness",
        value_type="float",
        category="religion",
        default_enabled=True,
        description="Sanjiao religion mechanic",
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
        default_enabled=True,
    ),
    FieldDef(
        key="score_dip",
        display_name="DIP Score",
        json_path="score.score_rating.DIP",
        value_type="float",
        category="score",
        default_enabled=True,
    ),
    FieldDef(
        key="score_mil",
        display_name="MIL Score",
        json_path="score.score_rating.MIL",
        value_type="float",
        category="score",
        default_enabled=True,
    ),
    FieldDef(
        key="score_rank_adm",
        display_name="ADM Score Rank",
        json_path="score.score_rank.ADM",
        value_type="int",
        category="score",
        default_enabled=False,
    ),
    FieldDef(
        key="score_rank_dip",
        display_name="DIP Score Rank",
        json_path="score.score_rank.DIP",
        value_type="int",
        category="score",
        default_enabled=False,
    ),
    FieldDef(
        key="score_rank_mil",
        display_name="MIL Score Rank",
        json_path="score.score_rank.MIL",
        value_type="int",
        category="score",
        default_enabled=False,
    ),
    FieldDef(
        key="age_score",
        display_name="Age Score",
        json_path="score.age_score",
        value_type="json",
        category="score",
        default_enabled=False,
        description="Cumulative score per age era (list of floats). Resets at age transitions.",
    ),

    # ── Demographics ──────────────────────────────────────────────────────
    FieldDef(
        key="population",
        display_name="Population (pop mass)",
        json_path="last_months_population",
        value_type="float",
        category="demographics",
        default_enabled=True,
        description="Pop-mass unit (raw save value; ×1000 = approximate headcount)",
        display_format="x1000",
    ),
    FieldDef(
        key="pop_count",
        display_name="Pop Count",
        json_path="counters.Pops",
        value_type="int",
        category="demographics",
        default_enabled=True,
        description="Distinct pop-object count (integer). Different metric from pop mass.",
    ),

    # ── Technology ────────────────────────────────────────────────────────
    FieldDef(
        key="advances",
        display_name="Advances",
        json_path="counters.Advances",
        value_type="int",
        category="technology",
        default_enabled=True,
        description="Total researched advances (primary tech level indicator)",
    ),
    # research_rate: path TBD — needs confirming from a real save via
    #   rakaly melt -c <save.eu5> | grep research_speed
    # Expected path: something like "modifiers.research_speed_modifier"
    # Uncomment and set json_path once confirmed:
    # FieldDef(
    #     key="research_rate",
    #     display_name="Research Rate",
    #     json_path="???",
    #     value_type="float",
    #     category="technology",
    #     default_enabled=True,
    #     description="Research speed modifier (1–3); higher = faster advance acquisition",
    # ),

    # ── Counters (cumulative lifetime stats) ─────────────────────────────
    FieldDef(
        key="counter_locations",
        display_name="Locations",
        json_path="counters.Locations",
        value_type="int",
        category="counters",
        default_enabled=True,
        description="Number of owned locations",
    ),
    FieldDef(
        key="counter_border_locations",
        display_name="Border Locations",
        json_path="counters.BorderLocations",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_coastal_locations",
        display_name="Coastal Locations",
        json_path="counters.CoastalLocations",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_discovered_locations",
        display_name="Discovered Locations",
        json_path="counters.DiscoveredLocations",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_diplomacy",
        display_name="Diplomacy Actions",
        json_path="counters.Diplomacy",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_wars",
        display_name="Wars (lifetime)",
        json_path="counters.Wars",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_sieges",
        display_name="Sieges (lifetime)",
        json_path="counters.Siege",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_reforms",
        display_name="Reforms",
        json_path="counters.Reforms",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_rgo",
        display_name="RGO Count",
        json_path="counters.RGO",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_construction_started",
        display_name="Constructions Started",
        json_path="counters.ConstructionStarted",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_building_level_changed",
        display_name="Building Upgrades",
        json_path="counters.BuildingLevelChanged",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_works_of_art",
        display_name="Works of Art",
        json_path="counters.WorksOfArt",
        value_type="int",
        category="counters",
        default_enabled=False,
    ),
    FieldDef(
        key="counter_cabinet_card_modifier",
        display_name="Cabinet Card Modifiers",
        json_path="counters.CabinetCardModifier",
        value_type="int",
        category="counters",
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


# ---------------------------------------------------------------------------
# Field value resolution
# ---------------------------------------------------------------------------

def _walk_path(obj: Any, parts: list[str]) -> Any:
    """Walk a dot-path through nested dicts/lists. Returns None if path breaks."""
    node = obj
    for part in parts:
        if node is None:
            return None
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list):
            # Support negative indexing (e.g. "-1" for last element)
            try:
                idx = int(part)
                node = node[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return node


def _coerce(value: Any, value_type: str) -> Any:
    """Coerce a raw value to the expected type."""
    if value is None:
        return None
    if value_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if value_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if value_type == "str":
        return str(value) if value is not None else None
    if value_type == "json":
        # Pass through as-is — will be JSON-serialised in the snapshot blob
        return value
    if value_type == "list_len":
        # Return the length of a list
        if isinstance(value, list):
            return len(value)
        return None
    return value


def resolve_field_value(
    country_obj: dict,
    field: FieldDef,
    *,
    diplomacy_obj: dict | None = None,
    character_db: dict | None = None,
) -> Any:
    """
    Extract a field's value from a country object by following its json_path.

    Args:
        country_obj:   The country dict from countries.database[cid].
        field:         The field definition to extract.
        diplomacy_obj: The diplomacy dict from diplomacy_manager[cid] (optional).
        character_db:  The character_db.database dict (optional, for ruler/heir fields).

    Returns None if the path doesn't exist or the value can't be coerced.
    """
    path = field.json_path

    # --- @diplomacy: prefix → resolve from diplomacy_manager[cid] ---
    if path.startswith("@diplomacy:"):
        if diplomacy_obj is None:
            return None
        subpath = path[len("@diplomacy:"):]
        raw = _walk_path(diplomacy_obj, subpath.split("."))
        return _coerce(raw, field.value_type)

    # --- @ruler: / @heir: prefix → resolve via character_db ---
    if path.startswith("@ruler:") or path.startswith("@heir:"):
        if character_db is None:
            return None
        is_ruler = path.startswith("@ruler:")
        prefix_len = 7  # len("@ruler:") == len("@heir:") + 1... no
        if is_ruler:
            char_id = _walk_path(country_obj, ["government", "ruler"])
            subpath = path[7:]
        else:
            char_id = _walk_path(country_obj, ["government", "heir"])
            subpath = path[6:]
        if char_id is None:
            return None
        char_data = character_db.get(str(char_id))
        if not isinstance(char_data, dict):
            return None
        raw = _walk_path(char_data, subpath.split("."))
        return _coerce(raw, field.value_type)

    # --- Default: resolve from country object ---
    raw = _walk_path(country_obj, path.split("."))
    return _coerce(raw, field.value_type)
