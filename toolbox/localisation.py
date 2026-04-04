"""
localisation.py — Re-export wrapper

The canonical implementation lives at backend/parser/localisation.py.
This wrapper keeps toolbox scripts and notebooks working with existing imports.
"""

from backend.parser.localisation import load_localisation, display_name

__all__ = ["load_localisation", "display_name"]
