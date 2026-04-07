"""
geography_index.py — Static EU5 geographic hierarchy from map_data/definitions.txt

This module is loaded ONCE per playthrough at startup.  It parses the
``definitions.txt`` file found at::

    <game_install>/game/map_data/definitions.txt

That file is a Paradox-script tree describing the world hierarchy.  Five
nesting levels (using tab indentation) are present:

    continent          (depth 0,  ~9   entries)
    └─ sub_continent   (depth 1,  ~23  entries)
       └─ region       (depth 2,  ~82  entries)
          └─ area      (depth 3,  ~803 entries)
             └─ province_definition  (depth 4,  ~4 309 entries)
                └─ { location_slug location_slug ... }   ← bare leaf tokens

Sample::

    europe = {
        western_europe = {
            scandinavian_region = {
                svealand_area = {
                    uppland_province = { stockholm norrtalje enkoping ... }

The save itself provides the integer-id ↔ location-slug mapping (via
``metadata.compatibility.locations``) and the location ↔ province link
(via ``locations.locations[id].province`` + ``provinces.database[pid].
province_definition``), so we only need this file for the *upper* levels
of the hierarchy: province → area → region → sub_continent → continent.

Per project rule #5, this module never reads the file from anywhere
except the user's game install path passed in by the watcher config.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
#  Hand-written parser for definitions.txt
# ─────────────────────────────────────────────────────────────────────────
#
# We deliberately don't use a generic clauset parser here.  The grammar of
# this single file is restricted enough that a small recursive descent
# tokenizer is faster, easier to review, and produces clearer errors when
# a future game update changes the format.
#
# Grammar (simplified):
#
#     file       := node*
#     node       := IDENT '=' '{' (node | IDENT)* '}'
#     IDENT      := [a-zA-Z_][a-zA-Z0-9_]*
#
# Comments start with '#' and run to end of line.
# Whitespace is irrelevant except as a token separator.

_T_IDENT  = "IDENT"
_T_EQUALS = "="
_T_LBRACE = "{"
_T_RBRACE = "}"
_T_EOF    = "EOF"


def _tokenize(text: str) -> list[tuple[str, str, int]]:
    """Return a list of (kind, value, line_no) tokens.

    Kept simple and explicit so future changes are obvious.
    """
    tokens: list[tuple[str, str, int]] = []
    i = 0
    line = 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        if c == "#":
            # Comment to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "=":
            tokens.append((_T_EQUALS, c, line))
            i += 1
            continue
        if c == "{":
            tokens.append((_T_LBRACE, c, line))
            i += 1
            continue
        if c == "}":
            tokens.append((_T_RBRACE, c, line))
            i += 1
            continue
        # Identifier — letters, digits, underscore
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            tokens.append((_T_IDENT, text[i:j], line))
            i = j
            continue
        # Anything else is unexpected — record as a 1-char token so the
        # parser raises a clear error.
        raise ValueError(
            f"definitions.txt: unexpected character {c!r} at line {line}"
        )
    tokens.append((_T_EOF, "", line))
    return tokens


@dataclass
class _ParseState:
    tokens: list[tuple[str, str, int]]
    pos: int = 0

    def peek(self) -> tuple[str, str, int]:
        return self.tokens[self.pos]

    def eat(self, kind: str) -> tuple[str, str, int]:
        tok = self.tokens[self.pos]
        if tok[0] != kind:
            raise ValueError(
                f"definitions.txt: expected {kind} but got "
                f"{tok[0]} {tok[1]!r} at line {tok[2]}"
            )
        self.pos += 1
        return tok


# ─────────────────────────────────────────────────────────────────────────
#  GeographyIndex
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class GeographyIndex:
    """In-memory geographic hierarchy lookup.

    All maps use lowercase string slugs as both keys and values.  Use
    ``GeographyIndex.load(game_install_path)`` to populate one.
    """

    province_to_area:           dict[str, str] = field(default_factory=dict)
    area_to_region:             dict[str, str] = field(default_factory=dict)
    region_to_subcontinent:     dict[str, str] = field(default_factory=dict)
    subcontinent_to_continent:  dict[str, str] = field(default_factory=dict)

    # Fallback only — built from leaf tokens.  The save's authoritative
    # link is locations.locations[id].province → provinces.database[pid].
    # province_definition.  We keep this so callers can resolve a chain
    # from just a location slug if no save context is available
    # (e.g. a CLI tool).
    location_to_province:       dict[str, str] = field(default_factory=dict)

    # Bookkeeping
    source_path:                Path | None = None
    counts:                     dict[str, int] = field(default_factory=dict)

    # ---- Lookups -------------------------------------------------------

    def chain_for_province(self, province_def: str | None) -> dict[str, str | None]:
        """Return ``{province, area, region, sub_continent, continent}``
        for a province_definition slug.  Missing levels become ``None``.

        This is the main entry point used by the save extractor: it
        already knows the location → province link from the save itself
        and only needs the upper hierarchy.
        """
        if not province_def:
            return {
                "province":      None,
                "area":          None,
                "region":        None,
                "sub_continent": None,
                "continent":     None,
            }
        area  = self.province_to_area.get(province_def)
        reg   = self.area_to_region.get(area) if area else None
        sub   = self.region_to_subcontinent.get(reg) if reg else None
        cont  = self.subcontinent_to_continent.get(sub) if sub else None
        return {
            "province":      province_def,
            "area":          area,
            "region":        reg,
            "sub_continent": sub,
            "continent":     cont,
        }

    def chain_for_location(self, location_slug: str | None) -> dict[str, str | None]:
        """Resolve a complete chain starting from a location slug.

        Uses the leaf-token map built at parse time.  Falls back to all-
        ``None`` if the slug is unknown.
        """
        if not location_slug:
            return self.chain_for_province(None) | {"location": None}
        prov = self.location_to_province.get(location_slug)
        chain = self.chain_for_province(prov)
        chain["location"] = location_slug
        return chain

    def all_slugs(self) -> dict[str, set[str]]:
        """Return the unique slug set per level.  Used by the API
        endpoint to know which keys to send display names for."""
        return {
            "province_definition": set(self.province_to_area.keys()),
            "area":                set(self.area_to_region.keys()),
            "region":              set(self.region_to_subcontinent.keys()),
            "sub_continent":       set(self.subcontinent_to_continent.keys()),
            "continent":           set(self.subcontinent_to_continent.values()),
        }

    # ---- Loader --------------------------------------------------------

    @classmethod
    def load(cls, game_install_path: str | Path) -> "GeographyIndex":
        """Parse ``<install>/game/map_data/definitions.txt`` and return
        a fully built index.  Raises FileNotFoundError if the file is
        missing — the caller is expected to fall back to an empty index
        with a warning so the rest of the pipeline still runs."""
        root = Path(game_install_path)
        # Try the canonical location first, then a couple of common
        # variants seen in dev environments (game-data/eu5/in_game/...).
        candidates = [
            root / "game" / "map_data" / "definitions.txt",
            root / "map_data" / "definitions.txt",
            root / "in_game" / "map_data" / "definitions.txt",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise FileNotFoundError(
                f"definitions.txt not found under {root}.  Checked: "
                + ", ".join(str(c) for c in candidates)
            )

        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="windows-1252", errors="replace")

        tokens = _tokenize(text)
        state = _ParseState(tokens=tokens)
        index = cls(source_path=path)

        # File is a flat sequence of continent nodes at the top level.
        while state.peek()[0] != _T_EOF:
            cls._parse_continent(state, index)

        # Counts for log/diagnostics
        index.counts = {
            "continents":            len(set(index.subcontinent_to_continent.values())),
            "sub_continents":        len(index.subcontinent_to_continent),
            "regions":               len(index.region_to_subcontinent),
            "areas":                 len(index.area_to_region),
            "province_definitions":  len(index.province_to_area),
            "locations":             len(index.location_to_province),
        }

        logger.info(
            "GeographyIndex loaded from %s: %d continents, %d sub_continents, "
            "%d regions, %d areas, %d province_definitions, %d locations",
            path,
            index.counts["continents"],
            index.counts["sub_continents"],
            index.counts["regions"],
            index.counts["areas"],
            index.counts["province_definitions"],
            index.counts["locations"],
        )
        return index

    # ---- Recursive descent --------------------------------------------
    # Each _parse_X expects the cursor to be ON the IDENT token of that
    # level and consumes the full ``IDENT = { ... }`` block.

    @staticmethod
    def _parse_continent(state: _ParseState, idx: "GeographyIndex") -> None:
        cont_name = state.eat(_T_IDENT)[1]
        state.eat(_T_EQUALS)
        state.eat(_T_LBRACE)
        while state.peek()[0] != _T_RBRACE:
            sub_name = state.eat(_T_IDENT)[1]
            state.eat(_T_EQUALS)
            state.eat(_T_LBRACE)
            idx.subcontinent_to_continent[sub_name] = cont_name
            GeographyIndex._parse_subcontinent(state, idx, sub_name)
            state.eat(_T_RBRACE)
        state.eat(_T_RBRACE)

    @staticmethod
    def _parse_subcontinent(state: _ParseState, idx: "GeographyIndex", sub_name: str) -> None:
        while state.peek()[0] != _T_RBRACE:
            reg_name = state.eat(_T_IDENT)[1]
            state.eat(_T_EQUALS)
            state.eat(_T_LBRACE)
            idx.region_to_subcontinent[reg_name] = sub_name
            GeographyIndex._parse_region(state, idx, reg_name)
            state.eat(_T_RBRACE)

    @staticmethod
    def _parse_region(state: _ParseState, idx: "GeographyIndex", reg_name: str) -> None:
        while state.peek()[0] != _T_RBRACE:
            area_name = state.eat(_T_IDENT)[1]
            state.eat(_T_EQUALS)
            state.eat(_T_LBRACE)
            idx.area_to_region[area_name] = reg_name
            GeographyIndex._parse_area(state, idx, area_name)
            state.eat(_T_RBRACE)

    @staticmethod
    def _parse_area(state: _ParseState, idx: "GeographyIndex", area_name: str) -> None:
        while state.peek()[0] != _T_RBRACE:
            prov_name = state.eat(_T_IDENT)[1]
            state.eat(_T_EQUALS)
            state.eat(_T_LBRACE)
            idx.province_to_area[prov_name] = area_name
            # Province body is a flat list of bare location slugs.
            while state.peek()[0] != _T_RBRACE:
                loc_name = state.eat(_T_IDENT)[1]
                idx.location_to_province[loc_name] = prov_name
            state.eat(_T_RBRACE)


# ─────────────────────────────────────────────────────────────────────────
#  CLI smoke test
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m backend.parser.eu5.geography_index <game_install_path>")
        sys.exit(1)
    idx = GeographyIndex.load(sys.argv[1])
    print(f"Source: {idx.source_path}")
    for k, v in idx.counts.items():
        print(f"  {k:<22s} {v:>6d}")
    # Smoke samples
    for slug in ("stockholm", "uppsala", "uppland_province", "svealand_area"):
        if slug in idx.location_to_province:
            print(f"  chain[{slug}] = {idx.chain_for_location(slug)}")
        elif slug in idx.province_to_area:
            print(f"  chain[{slug}] = {idx.chain_for_province(slug)}")
