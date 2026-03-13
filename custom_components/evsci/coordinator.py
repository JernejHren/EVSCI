"""Enhanced EVSCI Coordinator - Universal Compatibility Version."""
import logging
import math
import datetime
import time
import asyncio
import re
from datetime import timedelta
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.helpers.template import Template

from .const import (
    DOMAIN,
    MODE_OFF,
    MODE_PV_ONLY,
    MODE_MIN_PV,
    MODE_DYNAMIC,
    MODE_MAX_POWER,
    MODE_SCHEDULE,
    MODE_NO_CHANGE,
    # Enhanced configuration
    CONF_CHARGER_TYPE,
    CONF_GRID_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_TARIFF_SENSOR,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_STATUS,
    CONF_EV_SOC_SENSOR,
    CONF_PHASES,
    CONF_MAX_FUSE,
    CONF_BUFFER,
    CONF_CONTROL_INTERVAL,
    CONF_AUTO_MODE,
    CONF_RESET_ON_UNPLUG,
    CONF_LIMIT_BLOCK_1,
    CONF_LIMIT_BLOCK_2,
    CONF_LIMIT_BLOCK_3,
    CONF_LIMIT_BLOCK_4,
    CONF_LIMIT_BLOCK_5,
    CONF_CURRENT_UNIT,
    CONF_GRID_SENSOR_INVERTED,
    CONF_USE_GRID_TEMPLATE,
    CONF_GRID_TEMPLATE,
    CONF_STATUS_CHARGING_VALUES,
    CONF_STATUS_CONNECTED_VALUES,
)

_LOGGER = logging.getLogger(__name__)

VOLTAGE = 230
MIN_AMPS = 6

# Safety constants
STALE_DATA_THRESHOLD = 60.0
RAMP_UP_STEP = 2.0


class EVSCICoordinator(DataUpdateCoordinator):
    """Enhanced coordinator with universal charger support."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.calculated_amp = 0
        self.is_charging = False
        
        self.user_target_soc = 100
        
        self.schedule_start = datetime.time(22, 0)
        self.schedule_end = datetime.time(6, 0)
        
        self._last_charger_status_val = None
        self._cable_connected = False
        
        # Energy tracking
        self._last_update_time = time.time()
        self.energy_inc_solar = 0.0
        self.energy_inc_grid = 0.0
        self.reset_session_flag = False
        
        # Rate limiting
        self._last_amp_change_time = 0.0
        
        # Tariff memory
        self._last_valid_tariff = 1
        
        # Grid template
        self._grid_template = None
        
        # Load config first
        self._load_config()
        
        # Initialize selected_mode based on auto_mode setting
        # If auto mode is set to something other than "No Change", 
        # check if cable is already connected and set that mode
        if self.auto_mode_on_plugin and self.auto_mode_on_plugin not in [MODE_NO_CHANGE, "No Change"]:
            # Check current charger status
            if self.charger_status_entity:
                status_state = self.hass.states.get(self.charger_status_entity)
                if status_state:
                    current_status = status_state.state
                    cable_connected = self._is_status_connected(current_status)
                    if cable_connected:
                        _LOGGER.info(f"EVSCI: Cable already connected at startup, setting mode to {self.auto_mode_on_plugin}")
                        self.selected_mode = self.auto_mode_on_plugin
                        self._cable_connected = True
                    else:
                        self.selected_mode = MODE_OFF
                else:
                    self.selected_mode = MODE_OFF
            else:
                self.selected_mode = MODE_OFF
        else:
            # No auto mode or set to "No Change" - start with OFF
            self.selected_mode = MODE_OFF

    def _load_config(self):
        """Load configuration with enhanced compatibility."""
        o = self.entry.options
        d = self.entry.data
        
        # Charger type
        self.charger_type = o.get(CONF_CHARGER_TYPE, d.get(CONF_CHARGER_TYPE, "generic"))
        
        # Entities
        self.grid_entity = o.get(CONF_GRID_SENSOR, d.get(CONF_GRID_SENSOR))
        self.solar_entity = o.get(CONF_SOLAR_SENSOR, d.get(CONF_SOLAR_SENSOR))
        self.tariff_entity = o.get(CONF_TARIFF_SENSOR, d.get(CONF_TARIFF_SENSOR))
        self.charger_switch_entity = o.get(CONF_CHARGER_SWITCH, d.get(CONF_CHARGER_SWITCH))
        self.charger_current_entity = o.get(CONF_CHARGER_CURRENT, d.get(CONF_CHARGER_CURRENT))
        self.charger_power_entity = o.get(CONF_CHARGER_POWER, d.get(CONF_CHARGER_POWER))
        self.charger_status_entity = o.get(CONF_CHARGER_STATUS, d.get(CONF_CHARGER_STATUS))
        self.ev_soc_entity = o.get(CONF_EV_SOC_SENSOR, d.get(CONF_EV_SOC_SENSOR))
        
        # Parameters
        self.phases = o.get(CONF_PHASES, d.get(CONF_PHASES, 3))
        self.max_fuse_amps = o.get(CONF_MAX_FUSE, d.get(CONF_MAX_FUSE, 25))
        self.buffer_watts = o.get(CONF_BUFFER, d.get(CONF_BUFFER, 500))
        self.control_interval = o.get(CONF_CONTROL_INTERVAL, d.get(CONF_CONTROL_INTERVAL, 30))
        
        self.auto_mode_on_plugin = o.get(CONF_AUTO_MODE, d.get(CONF_AUTO_MODE, MODE_NO_CHANGE))
        self.reset_on_unplug = o.get(CONF_RESET_ON_UNPLUG, d.get(CONF_RESET_ON_UNPLUG, False))
        
        # ENHANCED: Current unit conversion
        self.current_unit = o.get(CONF_CURRENT_UNIT, d.get(CONF_CURRENT_UNIT, "A"))
        
        # ENHANCED: Grid sensor options
        self.grid_sensor_inverted = o.get(CONF_GRID_SENSOR_INVERTED, d.get(CONF_GRID_SENSOR_INVERTED, False))
        self.use_grid_template = o.get(CONF_USE_GRID_TEMPLATE, d.get(CONF_USE_GRID_TEMPLATE, False))
        
        # ENHANCED: Status value parsing
        charging_str = o.get(CONF_STATUS_CHARGING_VALUES, d.get(CONF_STATUS_CHARGING_VALUES, "charging,Charging,C"))
        connected_str = o.get(CONF_STATUS_CONNECTED_VALUES, d.get(CONF_STATUS_CONNECTED_VALUES, "connected,Connected,B,B1,B2"))
        
        self.status_charging_values = [v.strip().lower() for v in charging_str.split(",") if v.strip()]
        self.status_connected_values = [v.strip().lower() for v in connected_str.split(",") if v.strip()]
        
        # Setup grid template if configured
        if self.use_grid_template:
            template_str = o.get(CONF_GRID_TEMPLATE, d.get(CONF_GRID_TEMPLATE))
            if template_str:
                self._grid_template = Template(template_str, self.hass)
        
        self.power_per_amp = VOLTAGE * self.phases

        self.block_limits = {
            1: o.get(CONF_LIMIT_BLOCK_1, d.get(CONF_LIMIT_BLOCK_1, 6000)),
            2: o.get(CONF_LIMIT_BLOCK_2, d.get(CONF_LIMIT_BLOCK_2, 6000)),
            3: o.get(CONF_LIMIT_BLOCK_3, d.get(CONF_LIMIT_BLOCK_3, 6000)),
            4: o.get(CONF_LIMIT_BLOCK_4, d.get(CONF_LIMIT_BLOCK_4, 6000)),
            5: o.get(CONF_LIMIT_BLOCK_5, d.get(CONF_LIMIT_BLOCK_5, 6000)),
        }

    def _get_grid_power(self):
        """Enhanced grid power reading with template support and inversion."""
        if self.use_grid_template and self._grid_template:
            try:
                result = self._grid_template.async_render()
                power = float(result)
                return -power if self.grid_sensor_inverted else power
            except Exception as e:
                _LOGGER.warning(f"EVSCI: Grid template error: {e}")
                return 0.0
        
        # Standard sensor reading
        grid_state = self.hass.states.get(self.grid_entity)
        if not grid_state:
            return 0.0
        
        try:
            power = float(grid_state.state)
            return -power if self.grid_sensor_inverted else power
        except (ValueError, TypeError) as err:
            _LOGGER.debug("EVSCI: Failed to parse grid sensor value '%s': %s", grid_state.state, err)
            return 0.0

    def _convert_current_to_amps(self, value):
        """Convert current value to Amps based on configured unit."""
        if self.current_unit == "mA":
            return value / 1000.0
        elif self.current_unit == "W":
            # Convert power to amps: W / (V * phases)
            return value / self.power_per_amp
        else:  # "A"
            return value

    def _convert_amps_to_current(self, amps):
        """Convert Amps to configured current unit."""
        if self.current_unit == "mA":
            return amps * 1000.0
        elif self.current_unit == "W":
            # Convert amps to power: A * V * phases
            return amps * self.power_per_amp
        else:  # "A"
            return amps

    def _status_matches(self, status_value, configured_values):
        """Match charger status against configured values (exact, token and ABB-like state codes)."""
        if not status_value:
            return False

        status_str = str(status_value).strip().lower()
        status_tokens = set(re.findall(r"[a-z0-9]+", status_str))

        for value in configured_values:
            configured = str(value).strip().lower()
            if not configured:
                continue

            if status_str == configured:
                return True

            if configured in status_tokens:
                return True

            # ABB/IEC style values such as "State B1 - ..." should match configured "1"
            if configured.isdigit() and re.search(rf"\b[a-z]+{re.escape(configured)}\b", status_str):
                return True

            # Phrase fallback for multi-word statuses (avoids single-letter false positives)
            if len(configured) > 2 and configured in status_str:
                return True

        return False

    def _is_status_charging(self, status_value):
        """Check if status indicates charging."""
        return self._status_matches(status_value, self.status_charging_values)

    def _is_status_connected(self, status_value):
        """Check if status indicates cable connected."""
        if not status_value:
            return False

        status_str = str(status_value).strip().lower()

        # Keep compatibility with v1.3 behavior: most non-idle states imply cable connected.
        disconnected_markers = {
            "0",
            "state a",
            "state a - idle",
            "idle",
            "unavailable",
            "unknown",
            "false",
            "no cable plugged",
        }
        if status_str in disconnected_markers:
            return False

        # Explicit configured matching first.
        if self._status_matches(status_value, self.status_connected_values):
            return True

        # Charging state always implies an active cable connection.
        if self._status_matches(status_value, self.status_charging_values):
            return True

        # ABB/IEC text statuses like "State B1 - EV Plug in, Pending authorization"
        # should count as connected unless they are explicit idle (State A).
        match = re.search(r"\bstate\s+([a-z])([0-9]*)\b", status_str)
        if match:
            return match.group(1) != "a"

        return False

    def _is_schedule_active(self):
        now = dt_util.now().time()
        start = self.schedule_start
        end = self.schedule_end
        if start <= end:
            return start <= now < end
        else:
            return now >= start or now < end

    async def _async_update_data(self):
        """Main control logic with enhanced compatibility."""
        self._load_config()
        
        now_time = time.time()
        time_diff = now_time - self._last_update_time
        self._last_update_time = now_time
        self.reset_session_flag = False

        # === 1. READ SENSORS & SAFETY ===
        grid_power = self._get_grid_power()
        data_is_stale = False

        # Check if grid data is fresh
        if not self.use_grid_template:
            grid_state = self.hass.states.get(self.grid_entity)
            if grid_state:
                time_diff_sensor = dt_util.now() - grid_state.last_updated
                if time_diff_sensor.total_seconds() > STALE_DATA_THRESHOLD:
                    data_is_stale = True
                    if self.selected_mode != MODE_OFF:
                        _LOGGER.warning(
                            f"EVSCI: Grid data stale ({time_diff_sensor.total_seconds():.0f}s)! Pausing."
                        )
            else:
                data_is_stale = True

        solar_power = self._get_float_state(self.solar_entity)
        
        raw_tariff = self._get_int_state(self.tariff_entity, -1)
        if 1 <= raw_tariff <= 5:
            self._last_valid_tariff = raw_tariff
            tariff = raw_tariff
        else:
            tariff = self._last_valid_tariff
        
        charger_real_power = self._get_float_state(self.charger_power_entity)
        
        # ENHANCED: Current reading with unit conversion
        charger_current_state = self.hass.states.get(self.charger_current_entity)
        if charger_current_state and charger_current_state.state.replace('.', '').replace('-', '').isdigit():
            raw_current = float(charger_current_state.state)
            current_hw_amps = self._convert_current_to_amps(raw_current)
        else:
            current_hw_amps = 6.0
        
        switch_state = self.hass.states.get(self.charger_switch_entity)
        self.is_charging = (switch_state.state == "on") if switch_state else False

        current_soc = 0
        soc_is_valid = False
        if self.ev_soc_entity:
            soc_state = self.hass.states.get(self.ev_soc_entity)
            if soc_state and str(soc_state.state).replace('.', '').isdigit():
                current_soc = int(float(soc_state.state))
                soc_is_valid = True

        # === 2. ENERGY TRACKING ===
        ev_grid_power_usage = 0.0
        ev_solar_power_usage = 0.0
        if charger_real_power > 0:
            if grid_power > 0:
                ev_grid_power_usage = min(charger_real_power, grid_power)
            else:
                ev_grid_power_usage = 0.0
            ev_solar_power_usage = charger_real_power - ev_grid_power_usage
            if ev_solar_power_usage < 0:
                ev_solar_power_usage = 0

        safe_time_diff = min(time_diff, 60.0)
        self.energy_inc_grid = (ev_grid_power_usage * safe_time_diff) / 3600000.0
        self.energy_inc_solar = (ev_solar_power_usage * safe_time_diff) / 3600000.0

        # === 3. CABLE CONNECTION LOGIC (ENHANCED) ===
        force_pause = False
        should_stop_session = False
        
        if self.charger_status_entity:
            status_state = self.hass.states.get(self.charger_status_entity)
            if status_state:
                current_status = status_state.state
                
                # ENHANCED: Use configured status values
                cable_now_connected = self._is_status_connected(current_status)
                
                # Auto-start on cable connection
                if cable_now_connected and not self._cable_connected:
                    _LOGGER.info(f"EVSCI: Cable connected (status: {current_status})")
                    if self.auto_mode_on_plugin != MODE_NO_CHANGE:
                        _LOGGER.info(f"EVSCI: Auto-switching to {self.auto_mode_on_plugin}")
                        self.selected_mode = self.auto_mode_on_plugin
                
                # Reset on cable disconnect
                if not cable_now_connected and self._cable_connected:
                    _LOGGER.info(f"EVSCI: Cable disconnected (status: {current_status})")
                    should_stop_session = True
                    if self.reset_on_unplug:
                        self.selected_mode = MODE_OFF
                        self.reset_session_flag = True
                        _LOGGER.info("EVSCI: Session reset on unplug")
                
                self._cable_connected = cable_now_connected
                self._last_charger_status_val = current_status

        # === 4. SOC LIMIT CHECK ===
        if soc_is_valid and self.user_target_soc < 100:
            if current_soc >= self.user_target_soc:
                force_pause = True
                should_stop_session = True
                if self.is_charging and self.selected_mode != MODE_OFF:
                    _LOGGER.debug(f"EVSCI: Target SoC reached ({current_soc}%)")

        # === 5. POWER LIMITS ===
        house_load = grid_power - charger_real_power
        fuse_limit_w = self.max_fuse_amps * self.power_per_amp
        block_limit_w = self.block_limits.get(tariff, 6000)
        
        if self.selected_mode in [MODE_DYNAMIC, MODE_SCHEDULE]:
            limit_base = block_limit_w
        else:
            limit_base = fuse_limit_w

        limit_increase = limit_base - self.buffer_watts
        limit_maintain = limit_base
        limit_emergency = limit_base + self.buffer_watts

        # === 6. TARGET CURRENT CALCULATION ===
        target_mode_amps = 0
        should_session_be_active = False

        if should_stop_session:
            target_mode_amps = 0
            should_session_be_active = False
        else:
            should_session_be_active = True
            
            if self.selected_mode in [MODE_MAX_POWER, MODE_DYNAMIC]:
                target_mode_amps = 32

            elif self.selected_mode == MODE_SCHEDULE:
                if self._is_schedule_active():
                    target_mode_amps = 32
                else:
                    target_mode_amps = 0

            elif self.selected_mode in [MODE_PV_ONLY, MODE_MIN_PV]:
                excess_w = charger_real_power - grid_power
                solar_amps = math.floor(excess_w / self.power_per_amp)
                if self.selected_mode == MODE_PV_ONLY:
                    target_mode_amps = solar_amps
                else:
                    target_mode_amps = max(MIN_AMPS, solar_amps)

        # === 7. FINALIZATION ===
        adjusted_amps = current_hw_amps
        
        amps_limit_maintain = math.floor((limit_maintain - house_load) / self.power_per_amp)
        amps_limit_increase = math.floor((limit_increase - house_load) / self.power_per_amp)
        
        amps_limit_maintain = min(amps_limit_maintain, self.max_fuse_amps)
        amps_limit_increase = min(amps_limit_increase, self.max_fuse_amps)

        # Candidate
        if data_is_stale:
            candidate_amps = 0
        else:
            candidate_amps = min(target_mode_amps, amps_limit_maintain)

        # A. DECREASING?
        if candidate_amps < current_hw_amps:
            if not self.is_charging:
                adjusted_amps = candidate_amps
            else:
                is_emergency = False
                current_total_amps = current_hw_amps + (house_load / self.power_per_amp)
                
                if current_total_amps > self.max_fuse_amps:
                    is_emergency = True
                if self.selected_mode != MODE_MAX_POWER and grid_power > limit_emergency:
                    is_emergency = True

                if is_emergency:
                    _LOGGER.info("EVSCI: Critical overload! Reducing immediately.")
                    if current_hw_amps > MIN_AMPS:
                        adjusted_amps = MIN_AMPS
                    else:
                        adjusted_amps = 0
                else:
                    time_since_change = now_time - self._last_amp_change_time
                    if time_since_change >= self.control_interval:
                        adjusted_amps = candidate_amps
                    else:
                        adjusted_amps = current_hw_amps

        # B. INCREASING?
        elif candidate_amps > current_hw_amps:
            safe_target_up = min(target_mode_amps, amps_limit_increase)
            
            if safe_target_up > current_hw_amps:
                time_since_change = now_time - self._last_amp_change_time
                is_startup = (current_hw_amps < MIN_AMPS and safe_target_up >= MIN_AMPS)
                
                if not self.is_charging:
                    adjusted_amps = safe_target_up if safe_target_up < MIN_AMPS else MIN_AMPS
                elif is_startup or time_since_change >= self.control_interval:
                    if is_startup:
                        adjusted_amps = safe_target_up if safe_target_up < MIN_AMPS else MIN_AMPS
                    else:
                        max_step = current_hw_amps + RAMP_UP_STEP
                        adjusted_amps = min(safe_target_up, max_step)
                else:
                    adjusted_amps = current_hw_amps
            else:
                adjusted_amps = current_hw_amps
        else:
            adjusted_amps = current_hw_amps

        # C. Minimum threshold
        if adjusted_amps < MIN_AMPS:
            adjusted_amps = 0

        self.calculated_amp = adjusted_amps
        
        # === 8. SWITCH STATE DECISION ===
        final_switch_state = False
        
        if self.is_charging:
            if should_session_be_active:
                final_switch_state = True
            else:
                final_switch_state = False
        else:
            if should_session_be_active and adjusted_amps >= MIN_AMPS:
                final_switch_state = True
            else:
                final_switch_state = False

        await self._apply_changes(adjusted_amps, final_switch_state, current_hw_amps)

        return {
            "grid_power": grid_power,
            "charger_power": charger_real_power,
            "tariff": tariff,
            "mode": self.selected_mode,
            "target_current": self.calculated_amp,
            "is_charging": self.is_charging,
            "safety_amps_limit": amps_limit_maintain,
            "data_is_stale": data_is_stale,
            "current_soc": current_soc if soc_is_valid else None,
            "energy_inc_grid": self.energy_inc_grid,
            "energy_inc_solar": self.energy_inc_solar,
            "reset_session": self.reset_session_flag,
            "charger_type": self.charger_type,
        }

    async def _apply_changes(self, target_amps, should_be_active, current_hw_amps):
        """Apply changes with enhanced unit conversion."""
        if target_amps != current_hw_amps:
            if self.is_charging or should_be_active:
                # ENHANCED: Convert amps to configured unit
                target_value = self._convert_amps_to_current(target_amps)
                current_value = self._convert_amps_to_current(current_hw_amps)
                
                _LOGGER.info(
                    f"EVSCI: Current {current_value:.1f}{self.current_unit} -> "
                    f"{target_value:.1f}{self.current_unit} ({target_amps}A)"
                )
                
                await self.hass.services.async_call(
                    "number",
                    SERVICE_SET_VALUE,
                    {
                        ATTR_ENTITY_ID: self.charger_current_entity,
                        "value": target_value
                    }
                )
                self._last_amp_change_time = time.time()

        if should_be_active and not self.is_charging:
            if target_amps > 0:
                _LOGGER.info("EVSCI: Start Session (Switch ON)")
                await self.hass.services.async_call(
                    "switch",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: self.charger_switch_entity}
                )
                if target_amps > 0:
                    await asyncio.sleep(1)
                    target_value = self._convert_amps_to_current(target_amps)
                    await self.hass.services.async_call(
                        "number",
                        SERVICE_SET_VALUE,
                        {
                            ATTR_ENTITY_ID: self.charger_current_entity,
                            "value": target_value
                        }
                    )
             
        elif not should_be_active and self.is_charging:
            if self._cable_connected:
                _LOGGER.info("EVSCI: End Session (Switch OFF)")
                await self.hass.services.async_call(
                    "switch",
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: self.charger_switch_entity}
                )
            else:
                _LOGGER.debug("EVSCI: Session inactive, cable unplugged. Skip switch OFF.")

    def _get_float_state(self, entity_id):
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        try:
            return float(state.state)
        except:
            return 0.0

    def _get_int_state(self, entity_id, default=0):
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        try:
            return int(float(state.state))
        except:
            return default

    def set_mode(self, mode):
        self.selected_mode = mode
        self.async_set_updated_data(self.data)
