"""Testi nastavitve, odstranitve, naprave in entitet z resničnim Home Assistantom."""
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.core import HomeAssistant

from custom_components.evsci.const import DOMAIN, MODE_DYNAMIC, MODE_OFF

from .ha_common import (
    CHARGER_CURRENT,
    GRID,
    entity_id_for,
    make_entry,
    refresh,
    set_input_states,
    setup_entry,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "charger_services")

ALL_UNIQUE = {
    "select": ["mode_select"],
    "sensor": [
        "target_curr", "mon_grid", "mon_tariff",
        "session_total", "session_solar", "session_grid",
        "lifetime_total", "lifetime_solar", "lifetime_grid",
    ],
    "number": ["target_soc", "low_tariff_block"],
    "time": ["schedule_start", "schedule_end"],
}


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_required_entity_missing(hass: HomeAssistant) -> None:
    set_input_states(hass)
    hass.states.async_remove(GRID)
    entry = await setup_entry(hass, make_entry())
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert GRID in entry.reason


async def test_setup_succeeds_once_entity_appears(hass: HomeAssistant) -> None:
    set_input_states(hass)
    hass.states.async_remove(CHARGER_CURRENT)
    entry = await setup_entry(hass, make_entry())
    assert entry.state is ConfigEntryState.SETUP_RETRY
    hass.states.async_set(CHARGER_CURRENT, "0")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_device_is_registered(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "EV Smart Charging"
    assert device.manufacturer == "EVSCI"


async def test_all_entities_created_with_unique_ids(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entries) == sum(len(v) for v in ALL_UNIQUE.values())
    for platform, suffixes in ALL_UNIQUE.items():
        for suffix in suffixes:
            assert entity_id_for(hass, entry, platform, suffix).startswith(f"{platform}.")


async def test_entities_belong_to_device_and_have_translated_names(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    entity_registry = er.async_get(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        assert registry_entry.device_id == device.id
        assert registry_entry.translation_key
        assert registry_entry.has_entity_name


async def test_entity_categories_and_default_visibility(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    registry = er.async_get(hass)
    grid_monitor = registry.async_get(entity_id_for(hass, entry, "sensor", "mon_grid"))
    assert grid_monitor.entity_category == "diagnostic"
    assert grid_monitor.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    for platform, suffix in (("number", "target_soc"), ("time", "schedule_start")):
        assert registry.async_get(entity_id_for(hass, entry, platform, suffix)).entity_category == "config"


async def test_mode_select_changes_mode(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    select_id = entity_id_for(hass, entry, "select", "mode_select")
    assert hass.states.get(select_id).state == MODE_OFF
    await hass.services.async_call(
        "select", "select_option", {"entity_id": select_id, "option": MODE_DYNAMIC}, blocking=True
    )
    assert entry.runtime_data.selected_mode == MODE_DYNAMIC
    assert hass.states.get(select_id).state == MODE_DYNAMIC


async def test_target_soc_and_low_tariff_numbers_update_coordinator(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    soc = entity_id_for(hass, entry, "number", "target_soc")
    block = entity_id_for(hass, entry, "number", "low_tariff_block")
    await hass.services.async_call("number", "set_value", {"entity_id": soc, "value": 80}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": block, "value": 2}, blocking=True)
    assert entry.runtime_data.user_target_soc == 80
    assert entry.runtime_data.user_low_tariff_block == 2
    assert hass.states.get(soc).state == "80"
    assert hass.states.get(block).state == "2"


async def test_schedule_times_update_coordinator(hass: HomeAssistant) -> None:
    import datetime

    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    start = entity_id_for(hass, entry, "time", "schedule_start")
    end = entity_id_for(hass, entry, "time", "schedule_end")
    await hass.services.async_call("time", "set_value", {"entity_id": start, "time": "23:30:00"}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": end, "time": "05:15:00"}, blocking=True)
    assert entry.runtime_data.schedule_start == datetime.time(23, 30)
    assert entry.runtime_data.schedule_end == datetime.time(5, 15)
    assert hass.states.get(start).state == "23:30:00"


async def test_target_current_sensor_follows_coordinator(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    sensor = entity_id_for(hass, entry, "sensor", "target_curr")
    assert hass.states.get(sensor).state == "0"


async def test_availability_follows_grid_signal(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    registry = er.async_get(hass)
    # diagnostični senzor omrežja je privzeto onemogočen: omogoči ga in ponovno naloži
    grid_monitor = entity_id_for(hass, entry, "sensor", "mon_grid")
    registry.async_update_entity(grid_monitor, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(grid_monitor).state == "1000.0"

    hass.states.async_set(GRID, "unavailable")
    await refresh(hass, entry)
    assert hass.states.get(grid_monitor).state == STATE_UNAVAILABLE
    # števci energije ostanejo na voljo
    assert hass.states.get(entity_id_for(hass, entry, "sensor", "lifetime_total")).state != STATE_UNAVAILABLE

    hass.states.async_set(GRID, "500")
    await refresh(hass, entry)
    assert hass.states.get(grid_monitor).state == "500.0"
