# EU5 — Game Overview

> This document grows as we discover and verify game concepts via base game config files.
> **Rule:** Nothing is documented here without a cited config file or verified source.

---

## Game Version Tested
- **1.1.10** (from autosave sample)

## Save File
- See [`save-schema.md`](save-schema.md) for the complete format analysis.

---

## Verified Concepts

*(Empty — populated as we find and cite base game config files)*

---

## Discovered But Unverified

| Observed string | Context | Likely meaning | Config file needed |
|----------------|---------|----------------|--------------------|
| `Upper Bavaria` | Pre-ZIP metadata | Player country display name | `common/countries/` or localisation |
| `age_3_discovery` | string_lookup | An age/era flag | `common/ages/` |
| `hundred_years_war.200_fire_only_once` | string_lookup | An event flag | `events/` |
| `flavor_sco.101_fire_only_once` | string_lookup | Scotland flavor event flag | `events/flavor_sco.txt`? |
| `pattern_quarterly_flag.dds` | CoA data | Flag pattern texture | `gfx/coat_of_arms/patterns/` |

---

## Config Files to Locate

| Category | Expected path (relative to EU5 install) | Purpose |
|----------|-----------------------------------------|---------|
| Countries | `common/countries/` | Country definitions, tags |
| Country tags | `common/country_tags/` | 3-letter tag → country mapping |
| Ages/Eras | `common/ages/` | Age definitions and flags |
| Events | `events/` | Event definitions |
| Localisation | `localisation/` | Display names for all objects |
| Technologies | `common/technologies/` | Tech tree definitions |
| CoA patterns | `gfx/coat_of_arms/patterns/` | Flag/shield pattern textures |

> ⚠️ Paths are **guesses** based on EU4/CK3 conventions. Verify against actual EU5 install before using.
