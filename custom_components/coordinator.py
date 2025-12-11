"""EVSCI Coordinator - Logika upravljanja."""
import logging
import math
import datetime
import time
import asyncio
from datetime import timedelta
from homeassistant.util import dt as dt_util

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID
from homeassistant.components.number import SERVICE_SET_VALUE

from .const import (
    DOMAIN, 
    MODE_OFF,
    MODE_PV_ONLY,
    MODE_MIN_PV,
    MODE_DYNAMIC,
    MODE_MAX_POWER,
    MODE_SCHEDULE,
    MODE_NO_CHANGE,
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
)

_LOGGER = logging.getLogger(__name__)

VOLTAGE = 230
MIN_AMPS = 6

# VARNOSTNE KONSTANTE
STALE_DATA_THRESHOLD = 60.0  
RAMP_UP_STEP = 2.0           

class EVSCICoordinator(DataUpdateCoordinator):
    """Glavni razred za upravljanje EV polnjenja."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.selected_mode = MODE_OFF
        self.calculated_amp = 0
        self.is_charging = False
        
        self.user_target_soc = 100 
        
        self.schedule_start = datetime.time(22, 0)
        self.schedule_end = datetime.time(6, 0)
        
        self._last_charger_status_val = None 
        self._cable_connected = False
        
        # Energija
        self._last_update_time = time.time()
        self.energy_inc_solar = 0.0
        self.energy_inc_grid = 0.0
        self.reset_session_flag = False
        
        # Rate Limiting
        self._last_amp_change_time = 0.0
        
        self._load_config()

    def _load_config(self):
        o = self.entry.options
        d = self.entry.data
        
        self.grid_entity = o.get(CONF_GRID_SENSOR, d.get(CONF_GRID_SENSOR))
        self.solar_entity = o.get(CONF_SOLAR_SENSOR, d.get(CONF_SOLAR_SENSOR))
        self.tariff_entity = o.get(CONF_TARIFF_SENSOR, d.get(CONF_TARIFF_SENSOR))
        self.charger_switch_entity = o.get(CONF_CHARGER_SWITCH, d.get(CONF_CHARGER_SWITCH))
        self.charger_current_entity = o.get(CONF_CHARGER_CURRENT, d.get(CONF_CHARGER_CURRENT))
        self.charger_power_entity = o.get(CONF_CHARGER_POWER, d.get(CONF_CHARGER_POWER))
        self.charger_status_entity = o.get(CONF_CHARGER_STATUS, d.get(CONF_CHARGER_STATUS))
        self.ev_soc_entity = o.get(CONF_EV_SOC_SENSOR, d.get(CONF_EV_SOC_SENSOR))
        
        self.phases = o.get(CONF_PHASES, d.get(CONF_PHASES, 3))
        self.max_fuse_amps = o.get(CONF_MAX_FUSE, d.get(CONF_MAX_FUSE, 25))
        self.buffer_watts = o.get(CONF_BUFFER, d.get(CONF_BUFFER, 500))
        self.control_interval = o.get(CONF_CONTROL_INTERVAL, d.get(CONF_CONTROL_INTERVAL, 30))
        
        self.auto_mode_on_plugin = o.get(CONF_AUTO_MODE, d.get(CONF_AUTO_MODE, MODE_NO_CHANGE))
        self.reset_on_unplug = o.get(CONF_RESET_ON_UNPLUG, d.get(CONF_RESET_ON_UNPLUG, False))
        
        self.power_per_amp = VOLTAGE * self.phases 

        self.block_limits = {
            1: o.get(CONF_LIMIT_BLOCK_1, d.get(CONF_LIMIT_BLOCK_1, 6000)),
            2: o.get(CONF_LIMIT_BLOCK_2, d.get(CONF_LIMIT_BLOCK_2, 6000)),
            3: o.get(CONF_LIMIT_BLOCK_3, d.get(CONF_LIMIT_BLOCK_3, 6000)),
            4: o.get(CONF_LIMIT_BLOCK_4, d.get(CONF_LIMIT_BLOCK_4, 6000)),
            5: o.get(CONF_LIMIT_BLOCK_5, d.get(CONF_LIMIT_BLOCK_5, 6000)),
        }

    def _is_schedule_active(self):
        now = dt_util.now().time()
        start = self.schedule_start
        end = self.schedule_end
        if start <= end:
            return start <= now < end
        else:
            return now >= start or now < end

    async def _async_update_data(self):
        """Glavna logika."""
        self._load_config()
        
        now_time = time.time()
        time_diff = now_time - self._last_update_time
        self._last_update_time = now_time
        self.reset_session_flag = False

        # --- 1. BRANJE SENZORJEV & VARNOST ---
        grid_state = self.hass.states.get(self.grid_entity)
        grid_power = 0.0
        data_is_stale = False

        if grid_state:
            try:
                grid_power = float(grid_state.state)
                time_diff_sensor = dt_util.now() - grid_state.last_updated
                if time_diff_sensor.total_seconds() > STALE_DATA_THRESHOLD:
                    data_is_stale = True
                    if self.selected_mode != MODE_OFF:
                        _LOGGER.warning(f"EVSCI: Podatki omrežja stari {time_diff_sensor.total_seconds():.0f}s! Pavza.")
            except:
                data_is_stale = True
        else:
            data_is_stale = True

        solar_power = self._get_float_state(self.solar_entity)
        tariff = self._get_int_state(self.tariff_entity, 1)
        if tariff < 1 or tariff > 5: tariff = 1
        
        charger_real_power = self._get_float_state(self.charger_power_entity)
        
        charger_current_state = self.hass.states.get(self.charger_current_entity)
        current_hw_amps = float(charger_current_state.state) if charger_current_state and charger_current_state.state.replace('.','').isdigit() else 6.0
        
        switch_state = self.hass.states.get(self.charger_switch_entity)
        self.is_charging = (switch_state.state == "on") if switch_state else False

        current_soc = 0
        soc_is_valid = False
        if self.ev_soc_entity:
            soc_state = self.hass.states.get(self.ev_soc_entity)
            if soc_state and soc_state.state.isdigit():
                current_soc = int(soc_state.state)
                soc_is_valid = True

        # --- 2. ENERGIJA ---
        ev_grid_power_usage = 0.0
        ev_solar_power_usage = 0.0
        if charger_real_power > 0:
            if grid_power > 0:
                ev_grid_power_usage = min(charger_real_power, grid_power)
            else:
                ev_grid_power_usage = 0.0
            ev_solar_power_usage = charger_real_power - ev_grid_power_usage
            if ev_solar_power_usage < 0: ev_solar_power_usage = 0

        safe_time_diff = min(time_diff, 60.0) 
        self.energy_inc_grid = (ev_grid_power_usage * safe_time_diff) / 3600000.0
        self.energy_inc_solar = (ev_solar_power_usage * safe_time_diff) / 3600000.0

        # --- 3. LOGIKA PRIKLOPA ---
        if self.charger_status_entity:
            status_state = self.hass.states.get(self.charger_status_entity)
            if status_state:
                current_status_val = status_state.state
                is_idle = current_status_val in ["0", "State A - Idle", "unavailable", "unknown", "False", "No cable plugged"]
                is_connected_now = not is_idle

                if is_connected_now and not self._cable_connected:
                    _LOGGER.info(f"EVSCI: Priklop kabla! Resetiram sejo.")
                    self.reset_session_flag = True
                    if self.auto_mode_on_plugin != MODE_NO_CHANGE:
                        self.selected_mode = self.auto_mode_on_plugin
                        self.async_set_updated_data(self.data)

                elif not is_connected_now and self._cable_connected:
                    _LOGGER.info("EVSCI: Odklop kabla!")
                    if self.reset_on_unplug:
                        self.selected_mode = MODE_OFF
                        self.async_set_updated_data(self.data)
                
                self._cable_connected = is_connected_now
                self._last_charger_status_val = current_status_val

        # --- OPTIMIZACIJA: SHORT CIRCUIT ZA MODE OFF ---
        if self.selected_mode == MODE_OFF:
            self.calculated_amp = 0
            # Pošljemo ukaz za izklop (tok 0, stikalo OFF)
            await self._apply_changes(0, False, current_hw_amps)
            
            # Vrni podatke (da senzorji delajo) in končaj
            return {
                "grid_power": grid_power,
                "charger_power": charger_real_power,
                "tariff": tariff,
                "mode": self.selected_mode,
                "target_current": 0,
                "is_charging": self.is_charging,
                "safety_amps_limit": 0,
                "data_is_stale": data_is_stale,
                "current_soc": current_soc if soc_is_valid else None,
                "energy_inc_grid": self.energy_inc_grid,
                "energy_inc_solar": self.energy_inc_solar,
                "reset_session": self.reset_session_flag
            }

        # --- 4. PREVERJANJE LIMITOV (SoC & Stale Data) ---
        force_pause = False
        should_stop_session = False

        if data_is_stale:
            force_pause = True
        
        if soc_is_valid and self.user_target_soc < 100:
            if current_soc >= self.user_target_soc:
                force_pause = True
                should_stop_session = True
                if self.is_charging and self.selected_mode != MODE_OFF:
                    _LOGGER.debug(f"EVSCI: Cilj dosežen ({current_soc}%).")

        # --- 5. DOLOČANJE LIMITOV MOČI ---
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

        # --- 6. IZRAČUN CILJNEGA TOKA ---
        target_mode_amps = 0
        should_session_be_active = False

        if should_stop_session: # SoC Limit
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

        # --- 7. FINALIZACIJA ---
        adjusted_amps = current_hw_amps
        
        # Izračun limitov v Amperih
        amps_limit_maintain = math.floor((limit_maintain - house_load) / self.power_per_amp)
        amps_limit_increase = math.floor((limit_increase - house_load) / self.power_per_amp)
        
        amps_limit_maintain = min(amps_limit_maintain, self.max_fuse_amps)
        amps_limit_increase = min(amps_limit_increase, self.max_fuse_amps)

        # Kandidat = Minimum med željo in varnostnim limitom
        if data_is_stale:
            candidate_amps = 0
        else:
            candidate_amps = min(target_mode_amps, amps_limit_maintain)

        # A. ZMANJŠEVANJE?
        if candidate_amps < current_hw_amps:
            
            # Ali je KRITIČNO? (Red Zone)
            is_emergency = False
            current_total_amps = current_hw_amps + (house_load / self.power_per_amp)
            
            if current_total_amps > self.max_fuse_amps: is_emergency = True
            if self.selected_mode != MODE_MAX_POWER and grid_power > limit_emergency: is_emergency = True

            if is_emergency:
                 _LOGGER.info("EVSCI: Kritična preobremenitev! Znižujem takoj.")
                 # Soft Emergency: Najprej na 6A, če ne gre, na 0A
                 if current_hw_amps > MIN_AMPS:
                     adjusted_amps = MIN_AMPS
                 else:
                     adjusted_amps = 0
            
            else:
                # Navadno zmanjšanje -> Čakaj interval
                time_since_change = now_time - self._last_amp_change_time
                if time_since_change >= self.control_interval:
                    adjusted_amps = candidate_amps
                else:
                    adjusted_amps = current_hw_amps

        # B. POVEČEVANJE?
        elif candidate_amps > current_hw_amps:
            # Preveri Green Zone (Buffer)
            safe_target_up = min(target_mode_amps, amps_limit_increase)
            
            if safe_target_up > current_hw_amps:
                time_since_change = now_time - self._last_amp_change_time
                is_startup = (current_hw_amps < MIN_AMPS and safe_target_up >= MIN_AMPS)
                
                if is_startup or time_since_change >= self.control_interval:
                    if is_startup:
                        adjusted_amps = safe_target_up if safe_target_up < MIN_AMPS else MIN_AMPS
                    else:
                        max_step = current_hw_amps + RAMP_UP_STEP
                        adjusted_amps = min(safe_target_up, max_step)
                else:
                    adjusted_amps = current_hw_amps
            else:
                adjusted_amps = current_hw_amps # Deadband

        else:
            adjusted_amps = current_hw_amps

        # C. Minimum in Pavza
        if adjusted_amps < MIN_AMPS:
            adjusted_amps = 0

        self.calculated_amp = adjusted_amps
        
        # --- 8. ODLOČANJE O STANJU STIKALA (NOVA LOGIKA VKLOPA) ---
        final_switch_state = False
        
        if self.is_charging:
            # Če je ON, ostane ON, dokler način želi (tudi pri 0A)
            if should_session_be_active:
                final_switch_state = True
            else:
                final_switch_state = False # Stop Session
        else:
            # Če je OFF, se vklopi SAMO če imamo dovolj toka (Start Threshold)
            if should_session_be_active and adjusted_amps >= MIN_AMPS:
                final_switch_state = True
            else:
                final_switch_state = False # Čakamo na pogoje

        await self._apply_changes(adjusted_amps, final_switch_state, current_hw_amps)

        return {
            "grid_power": grid_power,
            "charger_power": charger_real_power,
            "mode": self.selected_mode,
            "target_current": self.calculated_amp,
            "is_charging": self.is_charging,
            "safety_amps_limit": amps_limit_maintain,
            "data_is_stale": data_is_stale,
            "current_soc": current_soc if soc_is_valid else None,
            "energy_inc_grid": self.energy_inc_grid,
            "energy_inc_solar": self.energy_inc_solar,
            "reset_session": self.reset_session_flag
        }

    async def _apply_changes(self, target_amps, should_be_active, current_hw_amps):
        """Pošiljanje ukazov."""
        
        # 1. KRMILJENJE TOKA (0A = Pavza)
        if target_amps != current_hw_amps:
            if self.is_charging or should_be_active:
                _LOGGER.info(f"EVSCI: Tok {current_hw_amps}A -> {target_amps}A")
                await self.hass.services.async_call("number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: self.charger_current_entity, "value": target_amps})
                self._last_amp_change_time = time.time()

        # 2. STATUS STIKALA
        if should_be_active and not self.is_charging:
             _LOGGER.info("EVSCI: Start Session (Switch ON)")
             await self.hass.services.async_call("switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: self.charger_switch_entity})
             if target_amps > 0:
                 await asyncio.sleep(1)
                 await self.hass.services.async_call("number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: self.charger_current_entity, "value": target_amps})
             
        elif not should_be_active and self.is_charging:
             if self._cable_connected:
                 _LOGGER.info("EVSCI: End Session (Switch OFF)")
                 await self.hass.services.async_call("switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self.charger_switch_entity})
             else:
                 _LOGGER.debug("EVSCI: Session inactive, but cable unplugged. Skip switch OFF.")

    def _get_float_state(self, entity_id):
        if not entity_id: return 0.0
        state = self.hass.states.get(entity_id)
        try: return float(state.state)
        except: return 0.0

    def _get_int_state(self, entity_id, default=0):
        if not entity_id: return default
        state = self.hass.states.get(entity_id)
        try: return int(state.state)
        except: return default

    def set_mode(self, mode):
        self.selected_mode = mode
        self.async_set_updated_data(self.data)
