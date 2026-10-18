"""EVSCI Coordinator - Logika upravljanja."""
import logging
import datetime
import time
import asyncio
from datetime import timedelta
from homeassistant.util import dt as dt_util

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.number import SERVICE_SET_VALUE

from .const import (
    DOMAIN, 
    MODE_OFF,
    MODE_NO_CHANGE,
    CONF_GRID_SENSOR,
    CONF_TARIFF_SENSOR,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_STATUS,
    CONF_IDLE_STATUSES,
    DEFAULT_LOW_TARIFF_BLOCK,
    DEFAULT_IDLE_STATUSES,
    CONF_EV_SOC_SENSOR,
    CONF_PHASES,
    CONF_MAX_FUSE,
    CONF_BUFFER,
    CONF_CONTROL_INTERVAL,
    CONF_VOLTAGE,
    CONF_MIN_CURRENT,
    CONF_MAX_CURRENT,
    CONF_AUTO_MODE,
    CONF_RESET_ON_UNPLUG,
    CONF_LIMIT_BLOCK_1,
    CONF_LIMIT_BLOCK_2,
    CONF_LIMIT_BLOCK_3,
    CONF_LIMIT_BLOCK_4,
    CONF_LIMIT_BLOCK_5,
    DEFAULT_VOLTAGE,
    DEFAULT_MIN_CURRENT,
    DEFAULT_MAX_CURRENT,
    CONF_FUSE_PROTECTION,
    FUSE_PROTECTION_TOTAL,
    FUSE_PROTECTION_PER_PHASE,
    PHASE_SENSOR_KEYS,
    CONF_CHARGER_PHASE,
    CHARGER_PHASES,
)
from .logic import (
    CHARGING_POWER_THRESHOLD_W,
    STARTUP_GRACE_SECONDS,
    Inputs,
    Settings,
    decide,
    is_idle_status,
    parse_idle_statuses,
    split_energy_power,
    stable_min_charge_power,
)

_LOGGER = logging.getLogger(__name__)

# VARNOSTNE KONSTANTE
STALE_DATA_THRESHOLD = 60.0

class EVSCICoordinator(DataUpdateCoordinator):
    """Glavni razred za upravljanje EV polnjenja."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=5),
        )
        self.entry = entry
        self.selected_mode = MODE_OFF
        self.calculated_amp = 0
        self.is_charging = False
        self._session_active = False
        self._pv_only_paused = False
        # Označi, da je aktivna seja že dejansko tekla (>=6A / realna moč),
        # da lahko ločimo "resume iz pavze" od prvega zagona.
        self._session_had_active_charge = False
        
        self.user_target_soc = 100 
        self.user_low_tariff_block = DEFAULT_LOW_TARIFF_BLOCK
        self._tariff_seen_valid = False
        
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

        # Zagon: do kdaj velja "grace period" in kakšen tok smo nazadnje ukazali
        self._grace_until = 0.0
        self._last_commanded_amps = 0.0

        # Števec dejanskih izračunov; senzorji energije prištejejo prirastke
        # samo ob novem izračunu, ne ob vsakem ponovnem objavljanju podatkov.
        self._update_id = 0

        self._current_unreadable_logged = False
        self._phase_unavailable_logged = False
        self._grid_unavailable_logged = False

        # Spomin za tarifo
        self._last_valid_tariff = 1
        
        self._load_config()

    def missing_entities(self) -> list[str]:
        """Obvezne entitete, ki jih (še) ni v Home Assistantu. Prazen seznam = vse je tam."""
        required = [
            self.grid_entity,
            self.charger_current_entity,
            self.charger_power_entity,
        ]
        return [e for e in required if e and self.hass.states.get(e) is None]

    def _load_config(self):
        o = self.entry.options
        d = self.entry.data
        
        self.grid_entity = o.get(CONF_GRID_SENSOR, d.get(CONF_GRID_SENSOR))
        self.tariff_entity = o.get(CONF_TARIFF_SENSOR, d.get(CONF_TARIFF_SENSOR))
        self.charger_start_button_entity = o.get(CONF_CHARGER_START_BUTTON, d.get(CONF_CHARGER_START_BUTTON))
        self.charger_stop_button_entity = o.get(CONF_CHARGER_STOP_BUTTON, d.get(CONF_CHARGER_STOP_BUTTON))
        # Legacy switch support for backward compatibility with old entries.
        self.charger_switch_entity = o.get(CONF_CHARGER_SWITCH, d.get(CONF_CHARGER_SWITCH))
        self.charger_current_entity = o.get(CONF_CHARGER_CURRENT, d.get(CONF_CHARGER_CURRENT))
        self.charger_power_entity = o.get(CONF_CHARGER_POWER, d.get(CONF_CHARGER_POWER))
        self.charger_status_entity = o.get(CONF_CHARGER_STATUS, d.get(CONF_CHARGER_STATUS))
        self.ev_soc_entity = o.get(CONF_EV_SOC_SENSOR, d.get(CONF_EV_SOC_SENSOR))
        idle_text = o.get(CONF_IDLE_STATUSES, d.get(CONF_IDLE_STATUSES))
        if idle_text is None:
            idle_text = DEFAULT_IDLE_STATUSES
        self.idle_statuses = parse_idle_statuses(idle_text)
        
        self.phases = o.get(CONF_PHASES, d.get(CONF_PHASES, 3))
        self.max_fuse_amps = o.get(CONF_MAX_FUSE, d.get(CONF_MAX_FUSE, 25))
        self.buffer_watts = o.get(CONF_BUFFER, d.get(CONF_BUFFER, 500))
        self.control_interval = o.get(CONF_CONTROL_INTERVAL, d.get(CONF_CONTROL_INTERVAL, 30))
        
        self.auto_mode_on_plugin = o.get(CONF_AUTO_MODE, d.get(CONF_AUTO_MODE, MODE_NO_CHANGE))
        self.reset_on_unplug = o.get(CONF_RESET_ON_UNPLUG, d.get(CONF_RESET_ON_UNPLUG, False))
        
        self.voltage = o.get(CONF_VOLTAGE, d.get(CONF_VOLTAGE, DEFAULT_VOLTAGE))
        self.min_amps = o.get(CONF_MIN_CURRENT, d.get(CONF_MIN_CURRENT, DEFAULT_MIN_CURRENT))
        self.max_amps = o.get(CONF_MAX_CURRENT, d.get(CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT))

        self.power_per_amp = self.voltage * self.phases
        self.fuse_protection = o.get(CONF_FUSE_PROTECTION, d.get(CONF_FUSE_PROTECTION, FUSE_PROTECTION_TOTAL))
        self.phase_entities = [o.get(key, d.get(key)) for key in PHASE_SENSOR_KEYS]
        charger_phase_name = o.get(CONF_CHARGER_PHASE, d.get(CONF_CHARGER_PHASE)) or CHARGER_PHASES[0]
        charger_phase = CHARGER_PHASES.index(charger_phase_name) if charger_phase_name in CHARGER_PHASES else 0

        self.settings = Settings(
            phases=self.phases,
            voltage=self.voltage,
            min_amps=self.min_amps,
            max_amps=self.max_amps,
            max_fuse_amps=self.max_fuse_amps,
            buffer_watts=self.buffer_watts,
            control_interval=self.control_interval,
            per_phase=self.fuse_protection == FUSE_PROTECTION_PER_PHASE,
            charger_phase=charger_phase,
        )

        self.block_limits = {
            1: o.get(CONF_LIMIT_BLOCK_1, d.get(CONF_LIMIT_BLOCK_1, 6000)),
            2: o.get(CONF_LIMIT_BLOCK_2, d.get(CONF_LIMIT_BLOCK_2, 6000)),
            3: o.get(CONF_LIMIT_BLOCK_3, d.get(CONF_LIMIT_BLOCK_3, 6000)),
            4: o.get(CONF_LIMIT_BLOCK_4, d.get(CONF_LIMIT_BLOCK_4, 6000)),
            5: o.get(CONF_LIMIT_BLOCK_5, d.get(CONF_LIMIT_BLOCK_5, 6000)),
        }

    @staticmethod
    def _state_age_seconds(state):
        """Starost zadnjega poročila senzorja (last_reported se osveži tudi pri nespremenjeni vrednosti)."""
        last_seen = state.last_reported or state.last_updated
        return (dt_util.utcnow() - last_seen).total_seconds()

    def _read_phase_currents(self):
        """Tokovi L1-L3 (A) ali None, če katerega ni mogoče zanesljivo prebrati.

        None je pri zaščiti po fazah varno stanje (pavza), ker ne vemo, koliko
        prostora je na najbolj obremenjeni fazi. Tiho ignoriranje ni sprejemljivo.
        """
        values = []
        problem = None
        for name, entity_id in zip(("L1", "L2", "L3"), self.phase_entities):
            state = self.hass.states.get(entity_id) if entity_id else None
            value = self._parse_float(state.state) if state else None
            if value is None:
                problem = f"{name} ({entity_id or 'ni nastavljen'}) ni berljiv"
                break
            age = self._state_age_seconds(state)
            if age > STALE_DATA_THRESHOLD:
                problem = f"{name} ({entity_id}) je star {age:.0f}s"
                break
            values.append(value)

        if problem:
            if not self._phase_unavailable_logged:
                _LOGGER.warning("EVSCI: Tok po fazah: %s. Polnjenje v pavzi, dokler ni spet na voljo.", problem)
                self._phase_unavailable_logged = True
            return None
        if self._phase_unavailable_logged:
            _LOGGER.info("EVSCI: Tokovi po fazah so spet na voljo.")
            self._phase_unavailable_logged = False
        return tuple(values)

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
        self._update_id += 1

        # --- 1. BRANJE SENZORJEV & VARNOST ---
        grid_state = self.hass.states.get(self.grid_entity)
        grid_power = 0.0
        data_is_stale = False
        grid_problem = None

        if grid_state:
            try:
                grid_power = float(grid_state.state)
                # last_reported se osveži ob vsakem poročilu senzorja (tudi pri
                # nespremenjeni vrednosti), last_updated samo ob spremembi.
                age = self._state_age_seconds(grid_state)
                if age > STALE_DATA_THRESHOLD:
                    data_is_stale = True
                    grid_problem = f"podatki so stari {age:.0f} s"
            except (ValueError, TypeError):
                data_is_stale = True
                grid_problem = f"vrednost ni berljiva ({grid_state.state})"
        else:
            data_is_stale = True
            grid_problem = "entiteta ne obstaja"

        # Opozorilo samo enkrat ob izpadu in sporočilo ob vrnitvi (brez spamanja dnevnika).
        if grid_problem:
            if not self._grid_unavailable_logged and self.selected_mode != MODE_OFF:
                _LOGGER.warning(
                    "EVSCI: Senzor omrežja (%s): %s. Pavza, dokler ni spet na voljo.",
                    self.grid_entity, grid_problem,
                )
                self._grid_unavailable_logged = True
        elif self._grid_unavailable_logged:
            _LOGGER.info("EVSCI: Senzor omrežja (%s) je spet na voljo.", self.grid_entity)
            self._grid_unavailable_logged = False

        raw_tariff = self._get_int_state(self.tariff_entity, -1)
        if 1 <= raw_tariff <= 5:
            self._last_valid_tariff = raw_tariff
            self._tariff_seen_valid = True
            tariff = raw_tariff
        else:
            tariff = self._last_valid_tariff
        
        charger_real_power = self._get_float_state(self.charger_power_entity)
        
        # Če toka polnilnika ni mogoče prebrati (unavailable/unknown), ne
        # ugibamo vrednosti, ampak ostanemo v varnem stanju (glej spodaj).
        charger_current_state = self.hass.states.get(self.charger_current_entity)
        current_hw_amps = self._parse_float(charger_current_state.state) if charger_current_state else None
        current_unreadable = current_hw_amps is None
        if current_unreadable:
            current_hw_amps = 0.0

        switch_state = self.hass.states.get(self.charger_switch_entity) if self.charger_switch_entity else None
        is_charging_from_switch = (switch_state.state == "on") if switch_state else False
        is_charging_from_power = charger_real_power > CHARGING_POWER_THRESHOLD_W
        self.is_charging = self._session_active or is_charging_from_switch or is_charging_from_power

        # Spomin trenutne seje: ali je polnjenje že dejansko stabilno steklo.
        # Ne uporabimo samo nastavljenega toka, ker je po startu lahko kratek zamik
        # (tok je 6A, realna moč pa še ni narasla).
        stable_min_charge_w = stable_min_charge_power(self.settings)
        if self.is_charging and charger_real_power >= stable_min_charge_w:
            self._session_had_active_charge = True
        elif not self.is_charging:
            self._session_had_active_charge = False

        current_soc = 0
        soc_is_valid = False
        if self.ev_soc_entity:
            soc_state = self.hass.states.get(self.ev_soc_entity)
            soc_value = self._parse_float(soc_state.state) if soc_state else None
            if soc_value is not None and 0 <= soc_value <= 100:
                current_soc = int(round(soc_value))
                soc_is_valid = True

        # --- 2. ENERGIJA ---
        ev_grid_power_usage, ev_solar_power_usage = split_energy_power(charger_real_power, grid_power)

        safe_time_diff = min(time_diff, 60.0) 
        self.energy_inc_grid = (ev_grid_power_usage * safe_time_diff) / 3600000.0
        self.energy_inc_solar = (ev_solar_power_usage * safe_time_diff) / 3600000.0

                # --- 3. LOGIKA PRIKLOPA ---
        if self.charger_status_entity:
            status_state = self.hass.states.get(self.charger_status_entity)
            if status_state:
                current_status_val = status_state.state
                is_idle = is_idle_status(current_status_val, self.idle_statuses)
                is_connected_now = not is_idle

                # Prvi prebran status po restartu uporabimo samo za inicializacijo
                # (brez "plug event"), sicer bi ob zagonu prepisali uporabniški način.
                if self._last_charger_status_val is None:
                    self._cable_connected = is_connected_now
                    self._last_charger_status_val = current_status_val
                elif is_connected_now and not self._cable_connected:
                    _LOGGER.info(f"EVSCI: Priklop kabla! Resetiram sejo.")
                    self.reset_session_flag = True
                    if self.auto_mode_on_plugin != MODE_NO_CHANGE:
                        self.selected_mode = self.auto_mode_on_plugin
                        self.async_set_updated_data(self.data)

                elif not is_connected_now and self._cable_connected:
                    _LOGGER.info("EVSCI: Odklop kabla!")
                    self._session_active = False
                    if self.reset_on_unplug:
                        self.selected_mode = MODE_OFF
                        self.async_set_updated_data(self.data)
                
                self._cable_connected = is_connected_now
                self._last_charger_status_val = current_status_val

        def build_result(target_current, safety_amps_limit):
            return {
                "update_id": self._update_id,
                "grid_power": grid_power,
                "charger_power": charger_real_power,
                "tariff": tariff,
                "mode": self.selected_mode,
                "target_current": target_current,
                "is_charging": self.is_charging,
                "safety_amps_limit": safety_amps_limit,
                "data_is_stale": data_is_stale,
                "current_soc": current_soc if soc_is_valid else None,
                "energy_inc_grid": self.energy_inc_grid,
                "energy_inc_solar": self.energy_inc_solar,
                "reset_session": self.reset_session_flag,
            }

        # --- OPTIMIZACIJA: SHORT CIRCUIT ZA MODE OFF ---
        if self.selected_mode == MODE_OFF:
            self.calculated_amp = 0
            # Pošljemo ukaz za izklop (tok 0, stikalo OFF)
            await self._apply_changes(0, False, current_hw_amps)

            return build_result(0, 0)

        # --- VARNO STANJE: TOK POLNILNIKA NI BERLJIV ---
        # Toka ne ugibamo in ga ne spreminjamo, dokler entiteta ni spet berljiva.
        if current_unreadable:
            if not self._current_unreadable_logged:
                _LOGGER.warning(
                    "EVSCI: Tok polnilnika (%s) ni berljiv. Brez ukazov, dokler entiteta ni spet na voljo.",
                    self.charger_current_entity,
                )
                self._current_unreadable_logged = True
            self.calculated_amp = 0
            return build_result(0, 0)
        if self._current_unreadable_logged:
            _LOGGER.info("EVSCI: Tok polnilnika (%s) je spet berljiv.", self.charger_current_entity)
            self._current_unreadable_logged = False

        # --- 4. ODLOČITEV (čista funkcija, glej logic.py) ---
        soc_limit_reached = bool(
            soc_is_valid
            and self.user_target_soc < 100
            and current_soc >= self.user_target_soc
        )
        if soc_limit_reached and self.is_charging:
            _LOGGER.debug(f"EVSCI: Cilj dosežen ({current_soc}%).")

        phase_currents = self._read_phase_currents() if self.settings.per_phase else None

        decision = decide(
            self.settings,
            Inputs(
                mode=self.selected_mode,
                grid_power=grid_power,
                charger_power=charger_real_power,
                current_amps=current_hw_amps,
                is_charging=self.is_charging,
                data_is_stale=data_is_stale,
                soc_limit_reached=soc_limit_reached,
                schedule_active=self._is_schedule_active(),
                block_limit_w=self.block_limits.get(tariff, 6000),
                now=now_time,
                last_amp_change_time=self._last_amp_change_time,
                grace_until=self._grace_until,
                last_commanded_amps=self._last_commanded_amps,
                pv_only_paused=self._pv_only_paused,
                session_had_active_charge=self._session_had_active_charge,
                phase_currents=phase_currents,
                tariff_block=tariff,
                low_tariff_block=self.user_low_tariff_block,
                tariff_known=bool(self.tariff_entity) and self._tariff_seen_valid,
            ),
        )

        if decision.emergency:
            _LOGGER.info("EVSCI: Kritična preobremenitev! Znižujem takoj.")

        self._pv_only_paused = decision.pv_only_paused
        self.calculated_amp = decision.target_amps

        await self._apply_changes(decision.target_amps, decision.session_active, current_hw_amps)

        return build_result(self.calculated_amp, decision.safety_amps_limit)

    async def _apply_changes(self, target_amps, should_be_active, current_hw_amps):
        """Pošiljanje ukazov."""
        # Zagon ali nadaljevanje iz pavze (tok gre čez minimum): vključi grace period.
        if (
            target_amps >= self.min_amps
            and current_hw_amps < self.min_amps
            and (self.is_charging or should_be_active)
        ):
            self._grace_until = time.time() + STARTUP_GRACE_SECONDS

        if target_amps != current_hw_amps:
            if self.is_charging or should_be_active:
                _LOGGER.info(f"EVSCI: Tok {current_hw_amps}A -> {target_amps}A")
                await self.hass.services.async_call("number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: self.charger_current_entity, "value": target_amps})
                self._last_amp_change_time = time.time()
                self._last_commanded_amps = target_amps

        if should_be_active and not self.is_charging:
             if target_amps > 0: # Start Threshold
                 _LOGGER.info("EVSCI: Start Session (Button PRESS)")
                 await self._async_start_session()
                 if target_amps > 0:
                     await asyncio.sleep(1)
                     await self.hass.services.async_call("number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: self.charger_current_entity, "value": target_amps})
                     self._last_commanded_amps = target_amps
             
        elif not should_be_active and self.is_charging:
             if self._cable_connected:
                 _LOGGER.info("EVSCI: End Session (Button PRESS)")
                 await self._async_stop_session()
             else:
                 _LOGGER.debug("EVSCI: Session inactive, cable unplugged. Skip stop.")

    async def _async_press_button(self, entity_id):
        if not entity_id:
            return
        await self.hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id},
        )

    async def _async_start_session(self):
        if self.charger_start_button_entity:
            await self._async_press_button(self.charger_start_button_entity)
            self._session_active = True
            return
        if self.charger_switch_entity:
            await self.hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: self.charger_switch_entity})
            self._session_active = True
            return
        _LOGGER.warning("EVSCI: Missing charger start control entity.")

    async def _async_stop_session(self):
        if self.charger_stop_button_entity:
            await self._async_press_button(self.charger_stop_button_entity)
            self._session_active = False
            return
        if self.charger_switch_entity:
            await self.hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: self.charger_switch_entity})
            self._session_active = False
            return
        _LOGGER.warning("EVSCI: Missing charger stop control entity.")

    @staticmethod
    def _parse_float(value):
        """Vrne float ali None, če vrednosti ni mogoče prebrati (unavailable, unknown, ...)."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _get_float_state(self, entity_id):
        if not entity_id: return 0.0
        state = self.hass.states.get(entity_id)
        if state is None: return 0.0
        value = self._parse_float(state.state)
        return 0.0 if value is None else value

    def _get_int_state(self, entity_id, default=0):
        if not entity_id: return default
        state = self.hass.states.get(entity_id)
        if state is None: return default
        value = self._parse_float(state.state)
        return default if value is None else int(value)

    def set_mode(self, mode):
        self.selected_mode = mode
        self.async_set_updated_data(self.data)


type EVSCIConfigEntry = ConfigEntry[EVSCICoordinator]
