"""Config flow za EVSCI."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
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


def _clean_optional(user_input):
    """Prazna neobvezna polja zapiše kot None, da se v možnostih prepišejo stare vrednosti."""
    for key in CONTROL_OPTIONAL_FIELDS:
        if user_input.get(key) in [None, "", []]:
            user_input[key] = None
    return user_input


def _validate_controls(user_input):
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


def _entity_errors(hass, user_input, keys):
    """Preveri, da izbrane entitete obstajajo. Vrne (napake, nadomestila za opis)."""
    missing = [
        user_input[key]
        for key in keys
        if user_input.get(key) and hass.states.get(user_input[key]) is None
    ]
    if missing:
        return {"base": "entity_not_found"}, {"entity": ", ".join(missing)}
    return {}, {}


def _get_phases_schema(charger_phases):
    """Shema za senzorje toka po fazah. Faza polnilnika samo pri enofaznem polnilniku."""
    fields = {}
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


class EVSCIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obravnava config flow za EVSCI."""
    VERSION = 1

    def __init__(self):
        self._user_data = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EVSCIOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Prva namestitev."""
        errors = {}
        placeholders = {}
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

        schema = self._get_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_phases(self, user_input=None):
        """Dodaten korak: senzorji toka po fazah (samo pri zaščiti po fazah)."""
        errors = {}
        placeholders = {}
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

    def _get_schema(self):
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


class EVSCIOptionsFlowHandler(config_entries.OptionsFlow):
    """Obravnava spremembe nastavitev."""

    def __init__(self, config_entry):
        self._user_input = {}

    async def async_step_init(self, user_input=None):
        errors = {}
        placeholders = {}
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
        flow = EVSCIConfigFlow()
        schema = flow._get_schema()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current_config),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_phases(self, user_input=None):
        """Dodaten korak: senzorji toka po fazah."""
        errors = {}
        placeholders = {}
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
