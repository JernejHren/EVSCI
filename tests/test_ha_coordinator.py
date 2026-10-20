"""Testi koordinatorja, popravkov, diagnostike in obnove stanja z resničnim Home Assistantom."""
import datetime

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.evsci.const import (
    CONF_AUTO_MODE,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STOP_BUTTON,
    CONF_FUSE_PROTECTION,
    CONF_IDLE_STATUSES,
    CONF_RESET_ON_UNPLUG,
    CONF_TARIFF_SENSOR,
    DOMAIN,
    MODE_DYNAMIC,
    MODE_LOW_TARIFF,
    MODE_MAX_POWER,
    MODE_OFF,
)
from custom_components.evsci.diagnostics import async_get_config_entry_diagnostics

from .ha_common import (
    CHARGER_CURRENT,
    CHARGER_POWER,
    CHARGER_STATUS,
    GRID,
    PHASE_SENSORS,
    START_BUTTON,
    STOP_BUTTON,
    SWITCH,
    TARIFF,
    entity_id_for,
    install_clock,
    make_entry,
    refresh,
    set_input_states,
    set_phase_states,
    setup_entry as _setup_entry,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "charger_services")

CHARGING = "State C - Charging"


@pytest.fixture(autouse=True)
def _services(charger_services):
    charger_services_holder["services"] = charger_services


charger_services_holder: dict = {}


async def setup_entry(hass, entry):
    """Nastavi vnos in znova postavi posnemanje storitev (glej conftest)."""
    entry = await _setup_entry(hass, entry)
    charger_services_holder["services"].rearm()
    return entry


def has_issue(hass: HomeAssistant, entry, key: str) -> bool:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{key}_{entry.entry_id}") is not None


async def set_mode(coordinator, mode: str) -> None:
    coordinator.selected_mode = mode
    await coordinator.async_refresh()


# --------------------------------------------------------------------- ukazi polnilniku

async def test_off_mode_sends_no_start(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    assert charger_services.press == []
    assert entry.runtime_data.data["target_current"] == 0


async def test_start_presses_start_button_and_sets_current(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_MAX_POWER)

    assert [c.data["entity_id"] for c in charger_services.press] == [START_BUTTON]
    assert charger_services.set_value
    assert all(c.data["entity_id"] == CHARGER_CURRENT for c in charger_services.set_value)
    assert charger_services.set_value[-1].data["value"] >= 6
    assert entry.runtime_data._session_active


async def test_start_uses_switch_when_no_buttons(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    data = {CONF_CHARGER_START_BUTTON: None, CONF_CHARGER_STOP_BUTTON: None, CONF_CHARGER_SWITCH: SWITCH}
    entry = await setup_entry(hass, make_entry(data=data))
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    assert [c.data["entity_id"] for c in charger_services.turn_on] == [SWITCH]
    assert charger_services.press == []


async def test_stop_presses_stop_button_when_mode_off(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: CHARGING})
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    charger_services.press.clear()
    hass.states.async_set(CHARGER_POWER, "4000")
    await set_mode(entry.runtime_data, MODE_OFF)
    assert [c.data["entity_id"] for c in charger_services.press] == [STOP_BUTTON]
    assert not entry.runtime_data._session_active


async def test_stop_uses_switch_turn_off(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: CHARGING})
    data = {CONF_CHARGER_START_BUTTON: None, CONF_CHARGER_STOP_BUTTON: None, CONF_CHARGER_SWITCH: SWITCH}
    entry = await setup_entry(hass, make_entry(data=data))
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    hass.states.async_set(SWITCH, "on")
    hass.states.async_set(CHARGER_POWER, "4000")
    await set_mode(entry.runtime_data, MODE_OFF)
    assert [c.data["entity_id"] for c in charger_services.turn_off] == [SWITCH]


async def test_stop_skipped_when_cable_unplugged(hass, charger_services, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: CHARGING})
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    charger_services.press.clear()
    hass.states.async_set(CHARGER_STATUS, "State A - Idle")
    hass.states.async_set(CHARGER_POWER, "4000")
    await set_mode(entry.runtime_data, MODE_OFF)
    assert charger_services.press == []


async def test_missing_start_control_logs_warning(hass, caplog, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(
        hass, make_entry(data={CONF_CHARGER_START_BUTTON: None, CONF_CHARGER_STOP_BUTTON: None})
    )
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    assert "Missing charger start control" in caplog.text
    await entry.runtime_data._async_stop_session()
    assert "Missing charger stop control" in caplog.text


# --------------------------------------------------------------------- priklop kabla

async def test_plug_in_switches_to_configured_auto_mode(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry(data={CONF_AUTO_MODE: MODE_DYNAMIC}))
    assert entry.runtime_data.selected_mode == MODE_OFF
    hass.states.async_set(CHARGER_STATUS, "State B - Connected")
    await refresh(hass, entry)
    assert entry.runtime_data.selected_mode == MODE_DYNAMIC


async def test_unplug_resets_to_off_when_configured(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: CHARGING})
    entry = await setup_entry(hass, make_entry(data={CONF_RESET_ON_UNPLUG: True}))
    await set_mode(entry.runtime_data, MODE_DYNAMIC)
    hass.states.async_set(CHARGER_STATUS, "State A - Idle")
    await refresh(hass, entry)
    assert entry.runtime_data.selected_mode == MODE_OFF


async def test_unplug_keeps_mode_by_default(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: CHARGING})
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_DYNAMIC)
    hass.states.async_set(CHARGER_STATUS, "State A - Idle")
    await refresh(hass, entry)
    assert entry.runtime_data.selected_mode == MODE_DYNAMIC


async def test_custom_idle_statuses_are_respected(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_STATUS: "Pripravljen"})
    entry = await setup_entry(
        hass, make_entry(data={CONF_IDLE_STATUSES: "Pripravljen", CONF_AUTO_MODE: MODE_DYNAMIC})
    )
    assert entry.runtime_data._cable_connected is False
    hass.states.async_set(CHARGER_STATUS, "Charging")
    await refresh(hass, entry)
    assert entry.runtime_data.selected_mode == MODE_DYNAMIC


# --------------------------------------------------------------------- izpadi senzorjev

async def test_unreadable_charger_current_sends_no_commands(hass, charger_services, monkeypatch, caplog) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    hass.states.async_set(CHARGER_CURRENT, "unavailable")
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    assert charger_services.press == []
    assert charger_services.set_value == []
    assert entry.runtime_data.data["inputs_ok"] is False
    assert caplog.text.count("ni berljiv") == 1  # opozorilo samo enkrat
    await refresh(hass, entry)
    assert caplog.text.count("ni berljiv") == 1

    hass.states.async_set(CHARGER_CURRENT, "0")
    await refresh(hass, entry)
    assert "spet berljiv" in caplog.text


async def test_grid_outage_creates_repair_after_delay_and_clears(hass, monkeypatch) -> None:
    clock = install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_DYNAMIC)
    hass.states.async_set(GRID, "unavailable")
    await refresh(hass, entry)
    assert not has_issue(hass, entry, "grid_sensor_unavailable")

    clock.advance(301)
    await refresh(hass, entry)
    assert has_issue(hass, entry, "grid_sensor_unavailable")
    assert entry.runtime_data.data["grid_ok"] is False

    hass.states.async_set(GRID, "500")
    await refresh(hass, entry)
    assert not has_issue(hass, entry, "grid_sensor_unavailable")


async def test_grid_missing_and_stale_are_handled(hass, monkeypatch, caplog) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_DYNAMIC)
    hass.states.async_remove(GRID)
    data = await refresh(hass, entry)
    assert data["data_is_stale"] is True
    assert "entiteta ne obstaja" in caplog.text

    hass.states.async_set(GRID, "1000")
    await refresh(hass, entry)
    assert "spet na voljo" in caplog.text


async def test_charger_current_outage_creates_repair(hass, monkeypatch) -> None:
    clock = install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    hass.states.async_set(CHARGER_CURRENT, "unknown")
    await refresh(hass, entry)
    clock.advance(301)
    await refresh(hass, entry)
    assert has_issue(hass, entry, "charger_current_unavailable")


async def test_low_tariff_without_sensor_creates_repair_and_clears(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_LOW_TARIFF)
    assert has_issue(hass, entry, "low_tariff_no_sensor")
    await set_mode(entry.runtime_data, MODE_OFF)
    assert not has_issue(hass, entry, "low_tariff_no_sensor")


async def test_tariff_sensor_invalid_marks_unavailable_and_keeps_last_valid(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    hass.states.async_set(TARIFF, "4")
    entry = await setup_entry(hass, make_entry(data={CONF_TARIFF_SENSOR: TARIFF}))
    data = await refresh(hass, entry)
    assert data["tariff"] == 4 and data["tariff_ok"] is True
    hass.states.async_set(TARIFF, "unavailable")
    data = await refresh(hass, entry)
    assert data["tariff"] == 4 and data["tariff_ok"] is False


async def test_per_phase_missing_sensor_pauses_and_creates_repair(hass, charger_services, monkeypatch) -> None:
    clock = install_clock(monkeypatch)
    set_input_states(hass)
    set_phase_states(hass)
    data = {
        CONF_FUSE_PROTECTION: "per_phase",
        "phase_sensor_l1": PHASE_SENSORS[0],
        "phase_sensor_l2": PHASE_SENSORS[1],
        "phase_sensor_l3": PHASE_SENSORS[2],
    }
    entry = await setup_entry(hass, make_entry(data=data))
    await set_mode(entry.runtime_data, MODE_MAX_POWER)
    assert entry.runtime_data.data["inputs_ok"] is True
    assert entry.runtime_data.data["target_current"] >= 6

    hass.states.async_set(PHASE_SENSORS[1], "unavailable")
    result = await refresh(hass, entry)
    assert result["inputs_ok"] is False
    assert result["target_current"] == 0
    clock.advance(301)
    await refresh(hass, entry)
    assert has_issue(hass, entry, "phase_sensor_unavailable")

    hass.states.async_set(PHASE_SENSORS[1], "5")
    result = await refresh(hass, entry)
    assert result["inputs_ok"] is True
    assert not has_issue(hass, entry, "phase_sensor_unavailable")


async def test_unload_removes_repairs(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    await set_mode(entry.runtime_data, MODE_LOW_TARIFF)
    assert has_issue(hass, entry, "low_tariff_no_sensor")
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not has_issue(hass, entry, "low_tariff_no_sensor")


# --------------------------------------------------------------------- energija

async def test_energy_counters_accumulate_and_session_resets_on_plug(hass, monkeypatch) -> None:
    clock = install_clock(monkeypatch)
    set_input_states(hass, **{CHARGER_POWER: "2000", GRID: "500"})
    entry = await setup_entry(hass, make_entry())
    total = entity_id_for(hass, entry, "sensor", "session_total")
    lifetime = entity_id_for(hass, entry, "sensor", "lifetime_total")
    grid = entity_id_for(hass, entry, "sensor", "session_grid")
    solar = entity_id_for(hass, entry, "sensor", "session_solar")

    clock.advance(30)
    await refresh(hass, entry)
    assert float(hass.states.get(total).state) > 0
    assert float(hass.states.get(grid).state) > 0
    assert float(hass.states.get(solar).state) > 0
    before = float(hass.states.get(total).state)
    assert float(hass.states.get(lifetime).state) == pytest.approx(before)

    # ponovna objava istih podatkov ne sme podvojiti energije
    entry.runtime_data.async_set_updated_data(entry.runtime_data.data)
    await hass.async_block_till_done()
    assert float(hass.states.get(total).state) == pytest.approx(before)

    # priklop kabla ponastavi sejo, števec skozi celo življenje ostane
    hass.states.async_set(CHARGER_STATUS, "State B - Connected")
    clock.advance(30)
    await refresh(hass, entry)
    hass.states.async_set(CHARGER_STATUS, "State A - Idle")
    await refresh(hass, entry)
    hass.states.async_set(CHARGER_STATUS, "State B - Connected")
    await refresh(hass, entry)
    assert float(hass.states.get(lifetime).state) >= before


# --------------------------------------------------------------------- obnova stanja

async def test_state_is_restored_after_restart(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    ids = {}
    for platform, suffix in (
        ("select", "mode_select"), ("number", "target_soc"), ("number", "low_tariff_block"),
        ("time", "schedule_start"), ("time", "schedule_end"), ("sensor", "lifetime_total"),
    ):
        ids[suffix] = registry.async_get_or_create(
            platform, DOMAIN, f"{entry.entry_id}_{suffix}", config_entry=entry,
            suggested_object_id=f"restore_{suffix}",
        ).entity_id
    mock_restore_cache(hass, (
        State(ids["mode_select"], MODE_DYNAMIC),
        State(ids["target_soc"], "70"),
        State(ids["low_tariff_block"], "2"),
        State(ids["schedule_start"], "21:30:00"),
        State(ids["schedule_end"], "07:45:00"),
        State(ids["lifetime_total"], "12.5"),
    ))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.selected_mode == MODE_DYNAMIC
    assert coordinator.user_target_soc == 70
    assert coordinator.user_low_tariff_block == 2
    assert coordinator.schedule_start == datetime.time(21, 30)
    assert coordinator.schedule_end == datetime.time(7, 45)
    assert float(hass.states.get(ids["lifetime_total"]).state) == pytest.approx(12.5)


async def test_invalid_restored_values_are_ignored(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    ids = {}
    for platform, suffix in (
        ("number", "target_soc"), ("number", "low_tariff_block"),
        ("time", "schedule_start"), ("time", "schedule_end"), ("sensor", "lifetime_total"),
    ):
        ids[suffix] = registry.async_get_or_create(
            platform, DOMAIN, f"{entry.entry_id}_{suffix}", config_entry=entry,
            suggested_object_id=f"bad_{suffix}",
        ).entity_id
    mock_restore_cache(hass, (
        State(ids["target_soc"], "abc"),
        State(ids["low_tariff_block"], "unavailable"),
        State(ids["schedule_start"], "not-a-time"),
        State(ids["schedule_end"], "unknown"),
        State(ids["lifetime_total"], "xyz"),
    ))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert coordinator.user_target_soc == 100
    assert coordinator.user_low_tariff_block == 3
    assert coordinator.schedule_start == datetime.time(22, 0)
    assert coordinator.schedule_end == datetime.time(6, 0)
    assert float(hass.states.get(ids["lifetime_total"]).state) == 0.0


async def test_restored_numbers_are_clamped(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    soc = registry.async_get_or_create("number", DOMAIN, f"{entry.entry_id}_target_soc", config_entry=entry).entity_id
    block = registry.async_get_or_create("number", DOMAIN, f"{entry.entry_id}_low_tariff_block", config_entry=entry).entity_id
    mock_restore_cache(hass, (State(soc, "250"), State(block, "9")))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.user_target_soc == 100
    assert entry.runtime_data.user_low_tariff_block == 5


# --------------------------------------------------------------------- diagnostika

async def test_diagnostics_contains_expected_sections(hass, monkeypatch) -> None:
    install_clock(monkeypatch)
    set_input_states(hass)
    entry = await setup_entry(hass, make_entry())
    hass.states.async_remove(STOP_BUTTON)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["config_entry"]["data"]["grid_sensor"] == GRID
    assert result["settings"]["phases"] == 3
    assert result["runtime"]["mode"] == MODE_OFF
    assert result["runtime"]["idle_statuses"]
    assert result["last_result"]["grid_power"] == 1000.0
    assert result["input_states"]["grid"]["state"] == "1000"
    assert result["input_states"]["stop_button"]["state"] == "missing"
    assert result["input_states"]["tariff"] is None
