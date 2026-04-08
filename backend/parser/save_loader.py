"""
save_loader.py — EU5 save file loader

Calls the rakaly CLI to parse a .eu5 save file into JSON, then builds
resolved lookup tables from the save's own internal managers.

Key insight: the save is self-referential.
  - culture_manager.database[id] -> {culture_definition: "string_key", ...}
  - religion_manager.database[id] -> {key: "string_key", name: "string_key", ...}
  - countries.tags[id] -> "TAG"

These integer IDs can be resolved entirely from within the save JSON itself.
Localisation files are only needed for human-readable display names on top.

Usage:
    from backend.parser.save_loader import load_save
    save = load_save("path/to/save.eu5", rakaly_bin="bin/rakaly/rakaly")
    print(save.player_country_tag)           # "WUR"
    print(save.resolve_culture(1066))        # "upper_german_culture" (key)
    print(save.resolve_religion(12))         # "catholic" (key)
    print(save.country_name("WUR"))          # display name from loc
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EU5Save:
    """Parsed EU5 save with resolved lookups."""

    raw: dict                          # Full rakaly JSON
    culture_index: dict[int, str]      # int id -> culture_definition key
    religion_index: dict[int, str]     # int id -> religion key
    tag_index: dict[str, str]          # numeric_str -> TAG string
    loc: dict[str, str]                # localisation key -> display name
    scripted_loc: dict[str, str] = None  # type: ignore[assignment]
    # Scripted-template entries (values still contain $VAR$ placeholders).
    # Populated alongside ``loc`` when a loc_dir is supplied. Defaults to
    # an empty dict in __post_init__ so older callers that build an
    # EU5Save by hand continue to work.

    def __post_init__(self):
        if self.scripted_loc is None:
            self.scripted_loc = {}

    # Convenience properties
    @property
    def game_date(self) -> str:
        return self.raw.get("metadata", {}).get("date", "?")

    @property
    def game_version(self) -> str:
        return self.raw.get("metadata", {}).get("version", "?")

    @property
    def player_country_id(self) -> str:
        return str(self.raw.get("played_country", {}).get("country", ""))

    @property
    def player_country_tag(self) -> str:
        return self.tag_index.get(self.player_country_id, "?")

    @property
    def player_country_name(self) -> str:
        return self.raw.get("metadata", {}).get("player_country_name", "?")

    @property
    def player_name(self) -> str:
        return self.raw.get("played_country", {}).get("name", "?")

    @property
    def is_multiplayer(self) -> bool:
        return self.raw.get("metadata", {}).get("multiplayer", False)

    @property
    def current_age_key(self) -> str:
        return self.raw.get("current_age", "?")

    @property
    def current_age_name(self) -> str:
        return self.loc.get(self.current_age_key, self.current_age_key)

    def resolve_culture(self, culture_id: int | str) -> str:
        """int id -> culture string key (e.g. 'upper_german_culture')"""
        return self.culture_index.get(int(culture_id), f"culture_{culture_id}")

    def resolve_religion(self, religion_id: int | str) -> str:
        """int id -> religion string key (e.g. 'catholic')"""
        return self.religion_index.get(int(religion_id), f"religion_{religion_id}")

    def resolve_culture_name(self, culture_id: int | str) -> str:
        """int id -> human display name"""
        key = self.resolve_culture(culture_id)
        from backend.parser.localisation import display_name
        return display_name(self.loc, key)

    def resolve_religion_name(self, religion_id: int | str) -> str:
        """int id -> human display name"""
        key = self.resolve_religion(religion_id)
        from backend.parser.localisation import display_name
        return display_name(self.loc, key)

    def country_tag(self, country_id: int | str) -> str:
        """numeric country id -> TAG string"""
        return self.tag_index.get(str(country_id), f"#{country_id}")

    def country_display_name(self, tag: str) -> str:
        """TAG -> human display name from localisation (simple tag lookup).

        For countries that carry an override via the ``country_name`` field
        (dict form, scripted key, or plain string override — see
        ``docs/games/eu5/duplicate-tags.md`` Pattern-B discussion), use
        ``resolve_country_display_name`` below which walks the override
        chain before falling back to this method.
        """
        return self.loc.get(tag, tag)

    def resolve_country_display_name(
        self,
        country_id: int | str,
        fallback_tag: str | None = None,
    ) -> str:
        """Resolve a country's display name, honouring ``country_name`` overrides.

        Resolution order:
        1. If ``cdata["country_name"]`` is a **dict**, extract the inner
           ``name`` field and fall through to step 2. The dict wrapper also
           carries ``key.Adjective`` and ``bases.Base`` which feed the
           ``$ADJ$`` substitution below.
        2. If the ``name`` candidate is a recognised key in ``self.loc``
           (display-ready), use that value as the template.
        3. Else if it is a key in ``self.scripted_loc`` (contains
           ``$VAR$`` placeholders), use that value as the template and
           substitute placeholders against ``self.loc``, passing the
           parent-country adjective as ``$ADJ$`` when the dict form carries
           a ``bases.Base`` hint.
        4. Else fall back to ``self.loc.get(fallback_tag, fallback_tag)``.
        5. If the resolved template still contains unresolved ``$…$``
           tokens after substitution, fall back again to step 4 rather
           than showing a broken string in the UI.

        ``AAA*`` colonial placeholder countries whose ``country_name`` is a
        raw province slug (~76 cases in the dev save) are NOT handled here
        by design — they need a separate "Spanish colony of …" fallback
        rule which is deferred (see ``docs/games/eu5/duplicate-tags.md``).
        Such names fall through to the fallback_tag branch naturally.
        """
        from backend.parser.localisation import resolve_scripted_value

        cdata = self.country_data(country_id)
        cn = cdata.get("country_name") if isinstance(cdata, dict) else None
        fb_tag = fallback_tag or self.tag_index.get(str(country_id)) or ""
        tag_fallback = self.loc.get(fb_tag, fb_tag)

        # Colonial placeholder guard — DEFERRED (see duplicate-tags.md
        # "Open questions" #3). ``AAA*`` tags are pre-allocated colonial
        # country slots whose ``country_name`` is a raw province slug like
        # ``sumbawa_province``. Those slugs happen to be loc keys and would
        # otherwise resolve here to plain place names ("Sumbawa", "Surrey"),
        # bypassing the intended "Spanish colony of X"-style fallback rule
        # that is still TBD. Keep them pinned to the tag fallback until the
        # colonial rule lands.
        if fb_tag.startswith("AAA"):
            return tag_fallback

        # Step 1: unwrap dict form.
        name_candidate: str | None = None
        adj_override: str | None = None
        if isinstance(cn, dict):
            raw_name = cn.get("name")
            if isinstance(raw_name, str):
                name_candidate = raw_name
            bases = cn.get("bases")
            if isinstance(bases, dict):
                base_tag = bases.get("Base")
                if isinstance(base_tag, str):
                    adj_override = self.loc.get(f"{base_tag}_ADJ") or self.loc.get(base_tag)
        elif isinstance(cn, str):
            name_candidate = cn

        if not name_candidate:
            return tag_fallback

        # Step 2: plain loc hit.
        if name_candidate in self.loc:
            return self.loc[name_candidate]

        # Step 3: scripted template resolution.
        template = self.scripted_loc.get(name_candidate)
        if template:
            extra = {"ADJ": adj_override} if adj_override else None
            resolved = resolve_scripted_value(template, self.loc, extra=extra)
            # If substitution left unresolved tokens, prefer the tag fallback.
            if "$" not in resolved:
                return resolved

        # Step 4/5: fallback to tag-based display.
        return tag_fallback

    def country_data(self, country_id: int | str) -> dict:
        """Get raw country object by numeric id"""
        return self.raw["countries"]["database"].get(str(country_id), {})

    def player_country_data(self) -> dict:
        return self.country_data(self.player_country_id)

    def all_real_countries(self) -> list[tuple[str, str, dict]]:
        """Return [(country_id, tag, data)] for all Real countries."""
        result = []
        for cid, cdata in self.raw["countries"]["database"].items():
            if isinstance(cdata, dict) and cdata.get("country_type") == "Real":
                tag = self.tag_index.get(cid, f"#{cid}")
                result.append((cid, tag, cdata))
        return result


def load_save(
    save_path: str | Path,
    rakaly_bin: str | Path = "bin/rakaly/rakaly",
    loc_dir: str | Path | None = None,
    verbose: bool = False,
) -> EU5Save:
    """
    Parse an EU5 save file and return an EU5Save object.

    Args:
        save_path:  Path to the .eu5 save file
        rakaly_bin: Path to the rakaly CLI binary
        loc_dir:    Path to localisation dir (e.g. game-data/eu5/localization/english)
                    If None, display names fall back to raw keys
        verbose:    Print progress to stderr
    """
    save_path = Path(save_path)
    rakaly_bin = Path(rakaly_bin)

    if not save_path.exists():
        raise FileNotFoundError(f"Save file not found: {save_path}")
    if not rakaly_bin.exists():
        raise FileNotFoundError(f"rakaly binary not found: {rakaly_bin}")

    # --- Step 1: Parse save to JSON via rakaly ---
    if verbose:
        print(f"[save_loader] Parsing {save_path.name} via rakaly...", file=sys.stderr)

    result = subprocess.run(
        [str(rakaly_bin), "json", str(save_path)],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"rakaly failed (exit {result.returncode}):\n{result.stderr.decode()}"
        )

    raw = json.loads(result.stdout)
    if verbose:
        print("[save_loader] Parsed OK.", file=sys.stderr)

    # --- Step 2: Build culture index from save's own culture_manager ---
    culture_index: dict[int, str] = {}
    for cid_str, cdata in raw.get("culture_manager", {}).get("database", {}).items():
        if isinstance(cdata, dict):
            key = cdata.get("culture_definition") or cdata.get("name", f"culture_{cid_str}")
            culture_index[int(cid_str)] = key

    # --- Step 3: Build religion index from save's own religion_manager ---
    religion_index: dict[int, str] = {}
    for rid_str, rdata in raw.get("religion_manager", {}).get("database", {}).items():
        if isinstance(rdata, dict):
            key = rdata.get("key") or rdata.get("name", f"religion_{rid_str}")
            religion_index[int(rid_str)] = key

    # --- Step 4: Build tag index (numeric id -> TAG string) ---
    tag_index: dict[str, str] = {}
    for num_id, tag in raw.get("countries", {}).get("tags", {}).items():
        tag_index[str(num_id)] = tag

    # --- Step 5: Load localisation if provided ---
    loc: dict[str, str] = {}
    scripted_loc: dict[str, str] = {}
    if loc_dir is not None:
        from backend.parser.localisation import (
            load_localisation,
            load_scripted_localisation,
        )
        loc_dir = Path(loc_dir)
        if loc_dir.exists():
            if verbose:
                print(f"[save_loader] Loading localisation from {loc_dir}...", file=sys.stderr)
            loc = load_localisation(loc_dir)
            scripted_loc = load_scripted_localisation(loc_dir)
            if verbose:
                print(
                    f"[save_loader] Loaded {len(loc):,} regular + "
                    f"{len(scripted_loc):,} scripted localisation entries.",
                    file=sys.stderr,
                )
        else:
            print(f"[save_loader] Warning: loc_dir not found: {loc_dir}", file=sys.stderr)

    return EU5Save(
        raw=raw,
        culture_index=culture_index,
        religion_index=religion_index,
        tag_index=tag_index,
        loc=loc,
        scripted_loc=scripted_loc,
    )
