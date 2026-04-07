"""
save_metadata.py — Cheap extraction of save-file metadata.

Uses `rakaly melt -c` to stream plaintext output, reads only until the
metadata block closes, then terminates the subprocess.  This avoids parsing
the full gamestate JSON and is suitable for scanning large save folders.

EU5 melt format (first ~20 lines):
    SAV<binary-header>          ← line 1, always skip
    metadata={
        multiplayer=yes
        date=1520.1.4.8
        playthrough_id="c832299a-d810-47d8-a21a-3e5e710c98d9"
        playthrough_name="Upper Bavaria #dc5a8326"
        save_label="1520.1.4.8 - Upper Bavaria"
        version="1.1.10"
        ...
    }
    ...rest of save (never read)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Keys we want to pull from the metadata block
_WANT = frozenset({
    "playthrough_id",
    "date",
    "multiplayer",
    "playthrough_name",
    "save_label",
    "version",
})

# Matches:  key=value  or  key="value"  (value may be empty)
_KV = re.compile(r'^\s*(\w+)\s*=\s*(?:"([^"]*)"|([\w./:-]*))\s*$')


def extract_save_metadata(
    save_path: Path,
    rakaly_bin: Path,
) -> dict | None:
    """
    Extract only the metadata block from an EU5 save file.

    Runs `rakaly melt -c <file>`, reads stdout line-by-line until the
    metadata block closes, then terminates the process.

    Returns:
        dict with keys: playthrough_id, date, country_name, playthrough_name,
        multiplayer (bool), version — or None on failure.
    """
    try:
        proc = subprocess.Popen(
            [str(rakaly_bin), "melt", "-c", str(save_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
    except OSError:
        return None

    raw: dict[str, str] = {}
    depth = 0
    in_metadata = False

    try:
        for line in proc.stdout:
            stripped = line.strip()

            if not in_metadata:
                # The metadata block always starts at line 2
                if stripped.startswith("metadata="):
                    in_metadata = True
                    depth = 1
                continue

            # Track brace depth to know when the block ends
            depth += stripped.count("{") - stripped.count("}")
            if depth <= 0:
                break  # closed

            # Only parse direct children of metadata (depth == 1)
            if depth == 1:
                m = _KV.match(line)
                if m:
                    key = m.group(1)
                    val = m.group(2) if m.group(2) is not None else (m.group(3) or "")
                    if key in _WANT:
                        raw[key] = val
                # Early-exit once we have everything we need
                if _WANT.issubset(raw):
                    break

    except Exception:
        pass
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

    if not raw.get("playthrough_id"):
        return None

    # Derive a clean country name from playthrough_name: "Upper Bavaria #dc5a8326" → "Upper Bavaria"
    country_name = re.sub(r'\s*#\w+$', '', raw.get("playthrough_name", "")).strip()
    if not country_name:
        # Fall back to save_label: "1520.1.4.8 - Upper Bavaria" → "Upper Bavaria"
        label = raw.get("save_label", "")
        if " - " in label:
            country_name = label.split(" - ", 1)[1].strip()

    return {
        "playthrough_id": raw["playthrough_id"],
        "date":            raw.get("date", ""),
        "country_name":    country_name,
        "playthrough_name": raw.get("playthrough_name", ""),
        "multiplayer":     raw.get("multiplayer", "no").lower() == "yes",
        "version":         raw.get("version", ""),
    }
