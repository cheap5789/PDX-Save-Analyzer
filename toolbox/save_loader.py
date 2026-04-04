"""
save_loader.py — Re-export wrapper

The canonical implementation lives at backend/parser/save_loader.py.
This wrapper keeps toolbox scripts and notebooks working with existing imports.
"""

from backend.parser.save_loader import EU5Save, load_save

__all__ = ["EU5Save", "load_save"]
