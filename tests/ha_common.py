"""Skupna pomoč za teste z Home Assistantom (ni test sama)."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.evsci.const import (
    CONF_AUTO_MODE,
    CONF_BUFFER,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STATUS,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CONTROL_INTERVAL,
    CONF_FUSE_PROTECTION,
    CONF_GRID_SENSOR,
    CONF_LIMIT_BLOCK_1,
    CONF_LIMIT_BLOCK_2,
    CONF_LIMIT_BLOCK_3,
    CONF_LIMIT_BLOCK_4,
    CONF_LIMIT_BLOCK_5,
    CONF_MAX_FUSE,
    CONF_PHASES,
    CONF_RESET_ON_UNPLUG,
    DOMAIN,
    MODE_NO_CHANGE,
)

GRID = "sensor.grid_power"
CHARGER_POWER = "sensor.charger_power"
CHARGER_CURRENT = "number.charger_current"
CHARGER_STATUS = "sensor.charger_status"
START_BUTTON = "button.charger_start"
STOP_BUTTON = "button.charger_stop"
SWITCH = "switch.charger"
TARIFF = "sensor.tariff_block"
PHASE_SENSORS = ["sensor.phase_l1", "sensor.phase_l2", "sensor.phase_l3"]

# Vnos obrazca z gumbi in skupno zaščito (brez neobveznih polj).
USER_INPUT = {
    CONF_GRID_SENSOR: GRID,
    CONF_CHARGER_START_BUTTON: START_BUTTON,
    CONF_CHARGER_STOP_BUTTON: STOP_BUTTON,
    CONF_CHARGER_CURRENT: CHARGER_CURRENT,
    CONF_CHARGER_POWER: CHARGER_POWER,
    CONF_CHARGER_STATUS: CHARGER_STATUS,
    CONF_PHASES: 3,
    CONF_MAX_FUSE: 25,
    CONF_BUFFER: 500,
    CONF_CONTROL_INTERVAL: 30,
    CONF_FUSE_PROTECTION: "total",
    CONF_AUTO_MODE: MODE_NO_CHANGE,
    CONF_RESET_ON_UNPLUG: False,
    CONF_LIMIT_BLOCK_1: 6000,
    CONF_LIMIT_BLOCK_2: 7000,
    CONF_LIMIT_BLOCK_3: 8000,
    CONF_LIMIT_BLOCK_4: 9000,
    CONF_LIMIT_BLOCK_5: 10000,
}


def set_input_states(hass: HomeAssistant, **overrides: str) -> None:
    """Postavi vhodne entitete v stanje mirovanja. ``overrides`` prepiše vrednosti po imenu konstante."""
    states = {
        GRID: "1000",
        CHARGER_POWER: "0",
        CHARGER_CURRENT: "0",
        CHARGER_STATUS: "State A - Idle",
        START_BUTTON: "unknown",
        STOP_BUTTON: "unknown",
        SWITCH: "off",
    }
    states.update(overrides)
    for entity_id, value in states.items():
        if value is not None:
            hass.states.async_set(entity_id, value)


def set_phase_states(hass: HomeAssistant, l1="5", l2="5", l3="5") -> None:
    for entity_id, value in zip(PHASE_SENSORS, (l1, l2, l3)):
        hass.states.async_set(entity_id, value)


def make_entry(data: dict | None = None, options: dict | None = None, unique_id: str | None = CHARGER_CURRENT) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="EV Smart Charging",
        data={**USER_INPUT, **(data or {})},
        options=options or {},
        unique_id=unique_id,
    )


# ---------------------------------------------------------------- pomoč za teste setupa
import types  # noqa: E402

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402

import custom_components.evsci.coordinator as coordinator_module  # noqa: E402


class FakeClock:
    """Nadzorovan ``time.time()`` in ``asyncio.sleep`` v koordinatorju (da teste ne čakajo)."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def sleep(self, _seconds: float) -> None:
        return None


def install_clock(monkeypatch) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setattr(coordinator_module, "time", types.SimpleNamespace(time=clock.time))
    monkeypatch.setattr(coordinator_module, "asyncio", types.SimpleNamespace(sleep=clock.sleep))
    return clock


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id_for(hass: HomeAssistant, entry: MockConfigEntry, platform: str, suffix: str) -> str:
    """entity_id iz registra po unique_id (``<entry_id>_<suffix>``)."""
    registry = er.async_get(hass)
    found = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{suffix}")
    assert found is not None, f"{platform} {suffix} ni v registru"
    return found


async def refresh(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    return entry.runtime_data.data


__all__ = [name for name in dir() if not name.startswith("_")]
assert ConfigEntryState  # za uvoz v testih
