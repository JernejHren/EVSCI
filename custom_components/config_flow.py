"""Config flow za EVSCI."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_GRID_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_CHARGER_SWITCH,
    CONF_CHARGER_CURRENT,
    CONF_CHARGER_POWER,
    CONF_CHARGER_STATUS,
    CONF_EV_SOC_SENSOR,
    CONF_TARIFF_SENSOR,
    CONF_PHASES,
    CONF_MAX_FUSE,
    CONF_BUFFER,
    CONF_CONTROL_INTERVAL, # NOVO
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

class EVSCIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obravnava config flow za EVSCI."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EVSCIOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Prva namestitev."""
        if user_input is not None:
            return self.async_create_entry(title="EV Smart Charging", data=user_input)

        defaults = {
            CONF_PHASES: 3,
            CONF_MAX_FUSE: 25,
            CONF_BUFFER: 500,
            CONF_CONTROL_INTERVAL: 30, # Privzeto 30s
            CONF_LIMIT_BLOCK_1: 6000,
            CONF_LIMIT_BLOCK_2: 6000,
            CONF_LIMIT_BLOCK_3: 6000,
            CONF_LIMIT_BLOCK_4: 6000,
            CONF_LIMIT_BLOCK_5: 6000,
            CONF_AUTO_MODE: MODE_NO_CHANGE,
            CONF_RESET_ON_UNPLUG: False
        }

        schema = self._get_schema()
        return self.async_show_form(
            step_id="user", 
            data_schema=self.add_suggested_values_to_schema(schema, defaults), 
        )

    def _get_schema(self):
        """Vrne shemo."""
        return vol.Schema({
            # --- SENZORJI ---
            vol.Required(CONF_GRID_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
            vol.Required(CONF_CHARGER_SWITCH): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Required(CONF_CHARGER_CURRENT): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
            vol.Required(CONF_CHARGER_POWER): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
            vol.Required(CONF_CHARGER_STATUS): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_TARIFF_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            
            vol.Optional(CONF_SOLAR_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
            vol.Optional(CONF_EV_SOC_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig()),
            
            # --- PARAMETRI ---
            vol.Required(CONF_PHASES): vol.In([1, 3]),
            vol.Required(CONF_MAX_FUSE): int,
            vol.Required(CONF_BUFFER): int,
            
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
        pass

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            optional_fields = [CONF_SOLAR_SENSOR, CONF_EV_SOC_SENSOR]
            for key in optional_fields:
                if key not in user_input or user_input[key] in [None, "", []]:
                    user_input[key] = None

            return self.async_create_entry(title="", data=user_input)

        current_config = {**self.config_entry.data, **self.config_entry.options}
        flow = EVSCIConfigFlow()
        schema = flow._get_schema()

        return self.async_show_form(
            step_id="init", 
            data_schema=self.add_suggested_values_to_schema(schema, current_config)
        )
