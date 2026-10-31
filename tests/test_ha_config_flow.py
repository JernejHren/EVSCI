"""Testi config flowa, reconfigure in options flowa z resničnim Home Assistantom."""
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.evsci.const import (
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_PHASE,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CHARGER_SWITCH,
    CONF_FUSE_PROTECTION,
    CONF_GRID_SENSOR,
    CONF_MAX_FUSE,
    CONF_PHASES,
    DOMAIN,
)

from .ha_common import (
    CHARGER_CURRENT,
    GRID,
    PHASE_SENSORS,
    START_BUTTON,
    STOP_BUTTON,
    SWITCH,
    USER_INPUT,
    make_entry,
    set_input_states,
    set_phase_states,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

PHASE_INPUT = {
    "phase_sensor_l1": PHASE_SENSORS[0],
    "phase_sensor_l2": PHASE_SENSORS[1],
    "phase_sensor_l3": PHASE_SENSORS[2],
}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_user_flow_shows_form(hass: HomeAssistant) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow_total_creates_entry(hass: HomeAssistant) -> None:
    set_input_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(USER_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EV Smart Charging"
    assert result["data"][CONF_GRID_SENSOR] == GRID
    entry = result["result"]
    assert entry.unique_id == CHARGER_CURRENT
    await hass.async_block_till_done()


async def test_user_flow_per_phase_has_second_step(hass: HomeAssistant) -> None:
    set_input_states(hass)
    set_phase_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "phases"
    assert CONF_CHARGER_PHASE not in result["data_schema"].schema  # 3f polnilnik

    result = await hass.config_entries.flow.async_configure(result["flow_id"], PHASE_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["phase_sensor_l2"] == PHASE_SENSORS[1]
    await hass.async_block_till_done()


async def test_user_flow_single_phase_charger_asks_for_its_phase(hass: HomeAssistant) -> None:
    set_input_states(hass)
    set_phase_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_PHASES: 1, CONF_FUSE_PROTECTION: "per_phase"}
    )
    assert result["step_id"] == "phases"
    assert CONF_CHARGER_PHASE in result["data_schema"].schema
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**PHASE_INPUT, CONF_CHARGER_PHASE: "L2"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CHARGER_PHASE] == "L2"
    await hass.async_block_till_done()


async def test_user_flow_phase_step_rejects_missing_sensor(hass: HomeAssistant) -> None:
    set_input_states(hass)
    set_phase_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**PHASE_INPUT, "phase_sensor_l2": "sensor.does_not_exist"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "entity_not_found"}
    assert result["description_placeholders"] == {"entity": "sensor.does_not_exist"}


async def test_user_flow_switch_instead_of_buttons(hass: HomeAssistant) -> None:
    set_input_states(hass)
    data = {k: v for k, v in USER_INPUT.items() if k not in (CONF_CHARGER_START_BUTTON, CONF_CHARGER_STOP_BUTTON)}
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**data, CONF_CHARGER_SWITCH: SWITCH})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CHARGER_SWITCH] == SWITCH
    assert result["data"].get(CONF_CHARGER_START_BUTTON) is None
    await hass.async_block_till_done()


async def test_user_flow_requires_start_stop_control(hass: HomeAssistant) -> None:
    set_input_states(hass)
    data = {k: v for k, v in USER_INPUT.items() if k not in (CONF_CHARGER_START_BUTTON, CONF_CHARGER_STOP_BUTTON)}
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_start_stop"}


async def test_user_flow_only_one_button_is_not_enough(hass: HomeAssistant) -> None:
    set_input_states(hass)
    data = {k: v for k, v in USER_INPUT.items() if k != CONF_CHARGER_STOP_BUTTON}
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["errors"] == {"base": "no_start_stop"}


async def test_user_flow_rejects_missing_entity(hass: HomeAssistant) -> None:
    set_input_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_GRID_SENSOR: "sensor.missing"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "entity_not_found"}
    assert result["description_placeholders"] == {"entity": "sensor.missing"}


async def test_user_flow_can_be_corrected_after_error(hass: HomeAssistant) -> None:
    set_input_states(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_GRID_SENSOR: "sensor.missing"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(USER_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_second_entry_for_same_charger_is_aborted(hass: HomeAssistant) -> None:
    set_input_states(hass)
    make_entry().add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(USER_INPUT))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_other_charger_is_allowed(hass: HomeAssistant) -> None:
    set_input_states(hass)
    hass.states.async_set("number.second_charger", "0")
    make_entry().add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_CHARGER_CURRENT: "number.second_charger"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


# ------------------------------------------------------------------ options flow

async def test_options_flow_updates_values(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {**USER_INPUT, CONF_MAX_FUSE: 20})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAX_FUSE] == 20
    assert result["data"]["phase_sensor_l1"] is None
    await hass.async_block_till_done()


async def test_options_flow_per_phase_two_steps(hass: HomeAssistant) -> None:
    set_input_states(hass)
    set_phase_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    assert result["step_id"] == "phases"
    result = await hass.config_entries.options.async_configure(result["flow_id"], PHASE_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["phase_sensor_l3"] == PHASE_SENSORS[2]
    await hass.async_block_till_done()


async def test_options_flow_phase_step_rejects_missing_sensor(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], PHASE_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "entity_not_found"}


async def test_options_flow_validates_controls_and_entities(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    no_controls = {k: v for k, v in USER_INPUT.items() if k not in (CONF_CHARGER_START_BUTTON, CONF_CHARGER_STOP_BUTTON)}
    result = await hass.config_entries.options.async_configure(result["flow_id"], no_controls)
    assert result["errors"] == {"base": "no_start_stop"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_GRID_SENSOR: "sensor.missing"}
    )
    assert result["errors"] == {"base": "entity_not_found"}


# ------------------------------------------------------------------ reconfigure

async def _reconfigure(hass: HomeAssistant, entry):
    return await entry.start_reconfigure_flow(hass)


async def test_reconfigure_total_replaces_data_and_clears_options(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry(options={CONF_MAX_FUSE: 16, "phase_sensor_l1": "sensor.old"})
    entry.add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER_INPUT, CONF_MAX_FUSE: 20})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.options == {}
    assert entry.data[CONF_MAX_FUSE] == 20
    assert entry.data["phase_sensor_l1"] is None
    await hass.async_block_till_done()


async def test_reconfigure_per_phase_two_steps(hass: HomeAssistant) -> None:
    set_input_states(hass)
    set_phase_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    assert result["step_id"] == "reconfigure_phases"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], PHASE_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_FUSE_PROTECTION] == "per_phase"
    assert entry.data["phase_sensor_l2"] == PHASE_SENSORS[1]
    await hass.async_block_till_done()


async def test_reconfigure_phase_step_rejects_missing_sensor(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_FUSE_PROTECTION: "per_phase"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], PHASE_INPUT)
    assert result["errors"] == {"base": "entity_not_found"}


async def test_reconfigure_rejects_charger_used_by_another_entry(hass: HomeAssistant) -> None:
    set_input_states(hass)
    hass.states.async_set("number.second_charger", "0")
    entry = make_entry()
    entry.add_to_hass(hass)
    make_entry(data={CONF_CHARGER_CURRENT: "number.second_charger"}, unique_id="number.second_charger").add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_CHARGER_CURRENT: "number.second_charger"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "charger_in_use"}


async def test_reconfigure_can_change_charger_and_updates_unique_id(hass: HomeAssistant) -> None:
    set_input_states(hass)
    hass.states.async_set("number.new_charger", "0")
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_CHARGER_CURRENT: "number.new_charger"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert entry.unique_id == "number.new_charger"
    await hass.async_block_till_done()


async def test_reconfigure_validates_controls_and_entities(hass: HomeAssistant) -> None:
    set_input_states(hass)
    entry = make_entry()
    entry.add_to_hass(hass)
    result = await _reconfigure(hass, entry)
    no_controls = {k: v for k, v in USER_INPUT.items() if k not in (CONF_CHARGER_START_BUTTON, CONF_CHARGER_STOP_BUTTON)}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], no_controls)
    assert result["errors"] == {"base": "no_start_stop"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_GRID_SENSOR: "sensor.missing"}
    )
    assert result["errors"] == {"base": "entity_not_found"}
