"""Skupna nastavitev testov.

Testi ``test_logic.py`` preverjajo čisto logiko in ne potrebujejo Home Assistanta.
Če HA ni nameščen, paket ``custom_components.evsci`` registriramo ročno (brez
izvajanja ``__init__.py``, ki uvaža HA), da se ``logic.py`` in ``const.py``
naložita samostojno. Če je nameščen ``pytest-homeassistant-custom-component``
(``pip install -r requirements_test.txt``), se naložijo tudi testi z resničnim
Home Assistantom.
"""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

try:
    import pytest_homeassistant_custom_component  # noqa: F401

    HAS_HA = True
    pytest_plugins = ["pytest_homeassistant_custom_component"]
except ImportError:
    HAS_HA = False
    for name, path in (
        ("custom_components", ROOT / "custom_components"),
        ("custom_components.evsci", ROOT / "custom_components" / "evsci"),
    ):
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            sys.modules[name] = module


def pytest_ignore_collect(collection_path, config):
    """Testi z Home Assistantom se brez HA preskočijo (ne podrejo zbiranja testov)."""
    if not HAS_HA and collection_path.name.startswith("test_ha_"):
        return True
    return None



if HAS_HA:
    from pytest_homeassistant_custom_component.common import async_mock_service

    @pytest.fixture
    def charger_services(hass):
        """Posnema storitve, ki jih koordinator kliče na polnilniku; klici se beležijo.

        ``rearm()`` ponovno registrira posnemanje po nalaganju integracije, ker
        platforma ``number`` ob zagonu registrira pravo storitev ``number.set_value``.
        """
        services = types.SimpleNamespace()

        def rearm() -> None:
            services.set_value = async_mock_service(hass, "number", "set_value")
            services.press = async_mock_service(hass, "button", "press")
            services.turn_on = async_mock_service(hass, "switch", "turn_on")
            services.turn_off = async_mock_service(hass, "switch", "turn_off")

        services.rearm = rearm
        rearm()
        return services
