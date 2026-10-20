"""Config flow za EVSCI."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_GRID_SENSOR,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_SWITCH,
    CONF_IDLE_STATUSES,
    DEFAULT_IDLE_STATUSES,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_STATUS,
    CONF_EV_SOC_SENSOR,
    CONF_TARIFF_SENSOR,
    CONF_PHASES,
    CONF_MAX_FUSE,
    CONF_BUFFER,
    CONF_CONTROL_INTERVAL,
    CONF_VOLTAGE,
    CONF_MIN_CURRENT,
    CONF_MAX_CURRENT,
    DEFAULT_VOLTAGE,
    DEFAULT_MIN_CURRENT,
    DEFAULT_MAX_CURRENT,
    CONF_FUSE_PROTECTION,
    FUSE_PROTECTION_TOTAL,
    FUSE_PROTECTION_PER_PHASE,
    FUSE_PROTECTION_MODES,
    PHASE_SENSOR_KEYS,
    CONF_CHARGER_PHASE,
    CHARGER_PHASES,
    CONF_AUTO_MODE,
    CONF_RESET_ON_UNPLUG,
    CONF_LIMIT_BLOCK_1,
    CONF_LIMIT_BLOCK_2,
    CONF_LIMIT_BLOCK_3,
    CONF_LIMIT_BLOCK_4,
    CONF_LIMIT_BLOCK_5,
    AUTO_MODES,
    MODE_NO_CHANGE
)

CONTROL_OPTIONAL_FIELDS = [
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CHARGER_SWITCH,
    CONF_TARIFF_SENSOR,
    CONF_EV_SOC_SENSOR,
]


def _clean_optional(user_input: dict[str, Any]) -> dict[str, Any]:
    """Prazna neobvezna polja zapiše kot None, da se v možnostih prepišejo stare vrednosti."""
    for key in CONTROL_OPTIONAL_FIELDS:
        if user_input.get(key) in [None, "", []]:
            user_input[key] = None
    return user_input


def _validate_controls(user_input: dict[str, Any]) -> dict[str, str]:
    """Polnilnik potrebuje stikalo ali par gumbov za start in stop."""
    has_buttons = bool(user_input.get(CONF_CHARGER_START_BUTTON)) and bool(
        user_input.get(CONF_CHARGER_STOP_BUTTON)
    )
    if has_buttons or user_input.get(CONF_CHARGER_SWITCH):
        return {}
    return {"base": "no_start_stop"}


ENTITY_FIELDS = [
    CONF_GRID_SENSOR,
    CONF_CHARGER_START_BUTTON,
    CONF_CHARGER_STOP_BUTTON,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_STATUS,
    CONF_TARIFF_SENSOR,
    CONF_EV_SOC_SENSOR,
]


def _entity_errors(
    hass: HomeAssistant, user_input: dict[str, Any], keys: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Preveri, da izbrane entitete obstajajo. Vrne (napake, nadomestila za opis)."""
    missing = [
        user_input[key]
        for key in keys
        if user_input.get(key) and hass.states.get(user_input[key]) is None
    ]
    if missing:
        return {"base": "entity_not_found"}, {"entity": ", ".join(missing)}
    return {}, {}


def _get_phases_schema(charger_phases: int) -> vol.Schema:
    """Shema za senzorje toka po fazah. Faza polnilnika samo pri enofaznem polnilniku."""
    fields: dict[Any, Any] = {}
    for key in PHASE_SENSOR_KEYS:
        fields[vol.Required(key)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="current")
        )
    if charger_phases == 1:
        fields[vol.Required(CONF_CHARGER_PHASE, default=CHARGER_PHASES[0])] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CHARGER_PHASES,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_CHARGER_PHASE,
            )
        )
    return vol.Schema(fields)


def _get_schema() -> vol.Schema:
    """Vrne shemo."""
    return vol.Schema({
        # --- SENZORJI ---
        vol.Required(CONF_GRID_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Optional(CONF_CHARGER_START_BUTTON): selector.EntitySelector(selector.EntitySelectorConfig(domain="button")),
        vol.Optional(CONF_CHARGER_STOP_BUTTON): selector.EntitySelector(selector.EntitySelectorConfig(domain="button")),
        vol.Optional(CONF_CHARGER_SWITCH): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        vol.Required(CONF_CHARGER_CURRENT): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
        vol.Required(CONF_CHARGER_POWER): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Required(CONF_CHARGER_STATUS): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(CONF_IDLE_STATUSES, default=DEFAULT_IDLE_STATUSES): str,

        vol.Optional(CONF_TARIFF_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(CONF_EV_SOC_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig()),

        # --- PARAMETRI ---
        vol.Required(CONF_PHASES): vol.In([1, 3]),
        vol.Required(CONF_MAX_FUSE): int,
        vol.Required(CONF_BUFFER): int,
        vol.Optional(CONF_VOLTAGE, default=DEFAULT_VOLTAGE): vol.All(int, vol.Range(min=100, max=480)),
        vol.Optional(CONF_MIN_CURRENT, default=DEFAULT_MIN_CURRENT): vol.All(int, vol.Range(min=1, max=32)),
        vol.Optional(CONF_MAX_CURRENT, default=DEFAULT_MAX_CURRENT): vol.All(int, vol.Range(min=6, max=80)),
        vol.Required(CONF_FUSE_PROTECTION, default=FUSE_PROTECTION_TOTAL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=FUSE_PROTECTION_MODES,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_FUSE_PROTECTION,
            )
        ),

        # NOVO: Interval
        vol.Required(CONF_CONTROL_INTERVAL): vol.All(int, vol.Range(min=5, max=300)),

        vol.Required(CONF_AUTO_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(options=AUTO_MODES, mode=selector.SelectSelectorMode.DROPDOWN)
        ),
        vol.Required(CONF_RESET_ON_UNPLUG): bool,

        # --- LIMITI ---
        vol.Required(CONF_LIMIT_BLOCK_1): int,
        vol.Required(CONF_LIMIT_BLOCK_2): int,
        vol.Required(CONF_LIMIT_BLOCK_3): int,
        vol.Required(CONF_LIMIT_BLOCK_4): int,
        vol.Required(CONF_LIMIT_BLOCK_5): int,
    })


class EVSCIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obravnava config flow za EVSCI."""
    VERSION = 1

    def __init__(self) -> None:
        self._user_data: dict[str, Any] = {}
        self._reconfigure_input: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry[Any]) -> EVSCIOptionsFlowHandler:
        return EVSCIOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Prva namestitev."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            user_input = _clean_optional(user_input)
            errors = _validate_controls(user_input)
            if not errors:
                errors, placeholders = _entity_errors(self.hass, user_input, ENTITY_FIELDS)
        if user_input is not None and not errors:
            # En polnilnik (entiteta za nastavitev toka) sme imeti samo en vnos.
            await self.async_set_unique_id(user_input[CONF_CHARGER_CURRENT])
            self._abort_if_unique_id_configured()
            if user_input.get(CONF_FUSE_PROTECTION) == FUSE_PROTECTION_PER_PHASE:
                self._user_data = user_input
                return await self.async_step_phases()
            return self.async_create_entry(title="EV Smart Charging", data=user_input)

        defaults = {
            CONF_PHASES: 3,
            CONF_MAX_FUSE: 25,
            CONF_BUFFER: 500,
            CONF_CONTROL_INTERVAL: 30, # Privzeto 30s
            CONF_VOLTAGE: DEFAULT_VOLTAGE,
            CONF_MIN_CURRENT: DEFAULT_MIN_CURRENT,
            CONF_MAX_CURRENT: DEFAULT_MAX_CURRENT,
            CONF_FUSE_PROTECTION: FUSE_PROTECTION_TOTAL,
            CONF_LIMIT_BLOCK_1: 6000,
            CONF_LIMIT_BLOCK_2: 6000,
            CONF_LIMIT_BLOCK_3: 6000,
            CONF_LIMIT_BLOCK_4: 6000,
            CONF_LIMIT_BLOCK_5: 6000,
            CONF_AUTO_MODE: MODE_NO_CHANGE,
            CONF_RESET_ON_UNPLUG: False,
            CONF_IDLE_STATUSES: DEFAULT_IDLE_STATUSES,
        }
        if user_input is not None:
            defaults = {**defaults, **user_input}

        schema = _get_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_phases(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Dodaten korak: senzorji toka po fazah (samo pri zaščiti po fazah)."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, placeholders = _entity_errors(self.hass, user_input, PHASE_SENSOR_KEYS)
            if not errors:
                return self.async_create_entry(
                    title="EV Smart Charging", data={**self._user_data, **user_input}
                )

        return self.async_show_form(
            step_id="phases",
            data_schema=_get_phases_schema(self._user_data.get(CONF_PHASES, 3)),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ponovna nastavitev obstoječega vnosa (iste nastavitve kot ob namestitvi)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            user_input = _clean_optional(user_input)
            errors = _validate_controls(user_input)
            if not errors:
                errors, placeholders = _entity_errors(self.hass, user_input, ENTITY_FIELDS)
            if not errors and self._charger_in_use_elsewhere(entry, user_input[CONF_CHARGER_CURRENT]):
                errors = {"base": "charger_in_use"}
            if not errors:
                self._reconfigure_input = user_input
                if user_input.get(CONF_FUSE_PROTECTION) == FUSE_PROTECTION_PER_PHASE:
                    return await self.async_step_reconfigure_phases()
                # Zaščita po skupni porabi: senzorjev po fazah ne potrebujemo.
                data = {**user_input, **{key: None for key in [*PHASE_SENSOR_KEYS, CONF_CHARGER_PHASE]}}
                return self._finish_reconfigure(entry, data)

        current_config = {**entry.data, **entry.options}
        if user_input is not None:
            current_config = {**current_config, **user_input}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(_get_schema(), current_config),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure_phases(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ponovna nastavitev: senzorji toka po fazah."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, placeholders = _entity_errors(self.hass, user_input, PHASE_SENSOR_KEYS)
            if not errors:
                return self._finish_reconfigure(entry, {**self._reconfigure_input, **user_input})

        current_config = {**entry.data, **entry.options}
        schema = _get_phases_schema(self._reconfigure_input.get(CONF_PHASES, 3))
        return self.async_show_form(
            step_id="reconfigure_phases",
            data_schema=self.add_suggested_values_to_schema(schema, current_config),
            errors=errors,
            description_placeholders=placeholders,
        )

    def _charger_in_use_elsewhere(self, entry: config_entries.ConfigEntry[Any], charger_current_entity: str) -> bool:
        """Ali isti polnilnik že uporablja drug vnos."""
        return any(
            other.entry_id != entry.entry_id and other.unique_id == charger_current_entity
            for other in self._async_current_entries()
        )

    def _finish_reconfigure(self, entry: config_entries.ConfigEntry[Any], data: dict[str, Any]) -> ConfigFlowResult:
        """Shrani nove nastavitve. Možnosti (options) se počistijo, ker bi sicer prepisale nove podatke.

        Ponovno nalaganje vnosa sproži poslušalec sprememb nastavitev.
        """
        self.hass.config_entries.async_update_entry(
            entry,
            unique_id=data[CONF_CHARGER_CURRENT],
            data=data,
            options={},
        )
        return self.async_abort(reason="reconfigure_successful")

class EVSCIOptionsFlowHandler(config_entries.OptionsFlow):
    """Obravnava spremembe nastavitev."""

    def __init__(self, config_entry: config_entries.ConfigEntry[Any]) -> None:
        self._user_input: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            user_input = _clean_optional(user_input)
            errors = _validate_controls(user_input)
            if not errors:
                errors, placeholders = _entity_errors(self.hass, user_input, ENTITY_FIELDS)
        if user_input is not None and not errors:
            if user_input.get(CONF_FUSE_PROTECTION) == FUSE_PROTECTION_PER_PHASE:
                self._user_input = user_input
                return await self.async_step_phases()

            # Zaščita po skupni porabi: senzorjev po fazah ne potrebujemo.
            for key in [*PHASE_SENSOR_KEYS, CONF_CHARGER_PHASE]:
                user_input[key] = None
            return self.async_create_entry(title="", data=user_input)

        current_config = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            current_config = {**current_config, **user_input}
        schema = _get_schema()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current_config),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_phases(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Dodaten korak: senzorji toka po fazah."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            errors, placeholders = _entity_errors(self.hass, user_input, PHASE_SENSOR_KEYS)
            if not errors:
                return self.async_create_entry(title="", data={**self._user_input, **user_input})

        current_config = {**self.config_entry.data, **self.config_entry.options}
        schema = _get_phases_schema(self._user_input.get(CONF_PHASES, 3))
        return self.async_show_form(
            step_id="phases",
            data_schema=self.add_suggested_values_to_schema(schema, current_config),
            errors=errors,
            description_placeholders=placeholders,
        )
