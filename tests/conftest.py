"""Skupna nastavitev testov.

``custom_components/evsci/__init__.py`` uvaža Home Assistant, ki ga za testiranje
čiste logike ne potrebujemo. Zato paket registriramo ročno (brez izvajanja
``__init__.py``), da se ``logic.py`` in ``const.py`` naložita samostojno.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.evsci", ROOT / "custom_components" / "evsci"),
):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
