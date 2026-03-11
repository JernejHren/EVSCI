"""Enhanced Config flow za EVSCI - Universal Compatibility Version."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

_LOGGER = logging.getLogger(__name__)

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
    CONF_CONTROL_INTERVAL,
    CONF_AUTO_MODE,
    CONF_RESET_ON_UNPLUG,
    CONF_LIMIT_BLOCK_1,
    CONF_LIMIT_BLOCK_2,
    CONF_LIMIT_BLOCK_3,
    CONF_LIMIT_BLOCK_4,
    CONF_LIMIT_BLOCK_5,
    AUTO_MODES,
    MODE_NO_CHANGE,
    MODE_SCHEDULE,  # Added for default
    # NEW CONSTANTS
    CONF_CHARGER_TYPE,
    CONF_CURRENT_UNIT,
    CONF_GRID_SENSOR_INVERTED,
    CONF_USE_GRID_TEMPLATE,
    CONF_GRID_TEMPLATE,
    CONF_STATUS_CHARGING_VALUES,
    CONF_STATUS_CONNECTED_VALUES,
    CURRENT_UNITS,  # Added this
)

CHARGER_TYPES = [
    "abb_terra",         # ABB Terra AC (Prvi na seznamu - tvoja polnilnica!)
    "generic",           # Standardna polnilnica (switch + number)
    "goe",              # go-eCharger
    "wallbox",          # Wallbox Pulsar/Commander
    "easee",            # Easee Home/Charge
    "zappi",            # myenergi Zappi
    "evse_din",         # EVSE DIN
    "openwb",           # OpenWB
    "tesla",            # Tesla Wall Connector
    "other_custom",     # Uporabniško definirano
]

class EVSCIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Enhanced config flow z boljšo kompatibilnostjo."""
    VERSION = 2  # Povečamo verzijo

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EVSCIOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Korak 1: Izbira tipa polnilnice."""
        if user_input is not None:
            self.charger_type = user_input.get(CONF_CHARGER_TYPE, "generic")
            return await self.async_step_charger_config()

        schema = vol.Schema({
            vol.Required(CONF_CHARGER_TYPE, default="generic"): vol.In(CHARGER_TYPES),
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "info": "Izberite tip vaše polnilnice za optimalno konfiguracijo. "
                        "Če vaše polnilnice ni na seznamu, izberite 'generic'."
            }
        )

    async def async_step_charger_config(self, user_input=None):
        """Korak 2: Konfiguracija polnilnice."""
        if user_input is not None:
            self.charger_config = user_input
            return await self.async_step_grid_config()

        # Poskusi avtomatsko najti entitete za znane polnilnice
        auto_entities = await self._auto_discover_charger_entities(self.charger_type)
        
        # Če so vse entitete najdene, preskoči ta korak
        if auto_entities and all(auto_entities.values()):
            _LOGGER.info(f"EVSCI: Auto-discovered {self.charger_type} entities: {auto_entities}")
            self.charger_config = auto_entities
            # Shrani tudi tip polnilnice
            self.charger_config[CONF_CHARGER_TYPE] = self.charger_type
            return await self.async_step_grid_config()
        
        # Prednastavitve glede na tip polnilnice
        presets = self._get_charger_presets(self.charger_type)
        
        # Uporabi najdene entitete kot defaults
        defaults = auto_entities if auto_entities else {}
        
        # Pripravi info sporočilo
        if auto_entities:
            found_entities = [k.replace("_", " ").title() for k, v in auto_entities.items() 
                            if k.startswith("charger_") and v]
            info_msg = (f"✅ Avtomatsko najdeno: {', '.join(found_entities)}. "
                       f"Preveri ali so entitete pravilne.")
        else:
            info_msg = f"Ročno vnesi entitete za {self.charger_type}."
        
        schema = vol.Schema({
            # --- OBVEZNI SENZORJI POLNILNICE ---
            vol.Required(CONF_CHARGER_SWITCH): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="switch",
                )
            ),
            vol.Required(CONF_CHARGER_CURRENT): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["number", "select"],
                )
            ),
            vol.Required(CONF_CHARGER_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power"
                )
            ),
            vol.Required(CONF_CHARGER_STATUS): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                )
            ),
            
            # --- OPCIJSKI SENZORJI ---
            vol.Optional(CONF_EV_SOC_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                )
            ),
            
            # --- NASTAVITVE ENOT ---
            vol.Required(CONF_CURRENT_UNIT, default=presets.get("unit", "A")): vol.In(CURRENT_UNITS),
            
            # --- VREDNOSTI STATUSA ---
            vol.Optional(
                CONF_STATUS_CHARGING_VALUES,
                default=presets.get("charging_values", "charging,Charging,C")
            ): str,
            vol.Optional(
                CONF_STATUS_CONNECTED_VALUES,
                default=presets.get("connected_values", "connected,Connected,B,B1,B2")
            ): str,
        })

        return self.async_show_form(
            step_id="charger_config",
            data_schema=self.add_suggested_values_to_schema(schema, defaults),
            description_placeholders={
                "info": info_msg
            }
        )

    async def async_step_grid_config(self, user_input=None):
        """Korak 3: Konfiguracija merilcev omrežja."""
        schema = self._get_grid_schema()
        info_text = (
            "Konfigurirajte senzorje omrežja.\n\n"
            "POMEMBNO:\n"
            "• Pozitivna vrednost (+) = uvoz iz omrežja\n"
            "• Negativna vrednost (-) = izvoz v omrežje (presežek)\n\n"
            "Če ima vaš merilec obratno logiko, označite 'Inverzna vrednost'.\n\n"
            "Za napredne uporabnike: uporabite template za kombinacijo več senzorjev."
        )

        if user_input is not None:
            if user_input.get(CONF_USE_GRID_TEMPLATE) and not user_input.get(CONF_GRID_TEMPLATE):
                return self.async_show_form(
                    step_id="grid_config",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "grid_template_required"},
                    description_placeholders={"info": info_text}
                )
            self.grid_config = user_input
            return await self.async_step_limits()

        return self.async_show_form(
            step_id="grid_config",
            data_schema=schema,
            description_placeholders={"info": info_text}
        )

    def _get_grid_schema(self):
        return vol.Schema({
            vol.Required(CONF_GRID_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_GRID_SENSOR_INVERTED, default=False): bool,
            vol.Optional(CONF_USE_GRID_TEMPLATE, default=False): bool,
            vol.Optional(CONF_GRID_TEMPLATE): selector.TemplateSelector(),
            vol.Optional(CONF_SOLAR_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_TARIFF_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        })

    async def async_step_limits(self, user_input=None):
        """Korak 4: Meje moči in kontrolni parametri."""
        if user_input is not None:
            # Združimo vse korake
            final_data = {
                CONF_CHARGER_TYPE: self.charger_type,
                **self.charger_config,
                **self.grid_config,
                **user_input
            }
            return self.async_create_entry(title="EV Smart Charging", data=final_data)

        schema = vol.Schema({
            # --- OSNOVNI PARAMETRI ---
            vol.Required(CONF_PHASES, default=3): vol.In([1, 3]),
            vol.Required(CONF_MAX_FUSE, default=25): vol.All(
                int, vol.Range(min=6, max=100)
            ),
            vol.Required(CONF_BUFFER, default=500): vol.All(
                int, vol.Range(min=0, max=2000)
            ),
            vol.Required(CONF_CONTROL_INTERVAL, default=30): vol.All(
                int, vol.Range(min=5, max=300)
            ),
            
            # --- AVTOMATIZACIJA ---
            vol.Required(CONF_AUTO_MODE, default=MODE_SCHEDULE): selector.SelectSelector(
                selector.SelectSelectorConfig(options=AUTO_MODES, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_RESET_ON_UNPLUG, default=False): bool,

            # --- TARIFNI BLOKI (NMPT ali drugi sistemi) ---
            vol.Required(CONF_LIMIT_BLOCK_1, default=6000): vol.All(
                int, vol.Range(min=1000, max=50000)
            ),
            vol.Required(CONF_LIMIT_BLOCK_2, default=6000): vol.All(
                int, vol.Range(min=1000, max=50000)
            ),
            vol.Required(CONF_LIMIT_BLOCK_3, default=6000): vol.All(
                int, vol.Range(min=1000, max=50000)
            ),
            vol.Required(CONF_LIMIT_BLOCK_4, default=6000): vol.All(
                int, vol.Range(min=1000, max=50000)
            ),
            vol.Required(CONF_LIMIT_BLOCK_5, default=6000): vol.All(
                int, vol.Range(min=1000, max=50000)
            ),
        })

        return self.async_show_form(
            step_id="limits",
            data_schema=schema,
            description_placeholders={
                "info": "Nastavite meje moči in kontrolne parametre.\n\n"
                        "AUTO MODE:\n"
                        "• Ko priključite kabel na avto, se bo samodejno aktiviral izbrani način polnjenja\n"
                        "• Schedule: Polni samo v določenem času (priporočeno za nočno polnjenje)\n"
                        "• Dynamic: Polni 24/7 glede na tarifni blok\n"
                        "• No Change: Način se ne spremeni (ročno upravljanje)\n\n"
                        "TARIFNI BLOKI:\n"
                        "• Slovenija (NMPT): nastavite različne limite za bloke 1-5\n"
                        "• Ena tarifa: vse bloke nastavite na enako vrednost (npr. 11000 W)\n"
                        "• Brez tarifnega sistema: uporabite dummy sensor s fiksno vrednostjo '1'"
            }
        )

    async def _auto_discover_charger_entities(self, charger_type):
        """Avtomatsko najde entitete za znane polnilnice."""
        import fnmatch
        
        # Definiraj vzorce iskanja za vsak tip polnilnice
        search_patterns = {
            "abb_terra": {
                "switch": ["switch.*abb*start*stop*", "switch.*abb*charging"],
                "current": ["number.*abb*current*limit"],
                "power": ["sensor.*abb*active*power", "sensor.*abb*power"],
                "status": ["sensor.*abb*charging*state", "sensor.*abb*state"],
            },
            "goe": {
                "switch": ["switch.*goe*", "switch.*go_e*"],
                "current": ["number.*goe*amp*", "number.*go_e*amp*", "number.*goe*current*"],
                "power": ["sensor.*goe*power", "sensor.*go_e*power"],
                "status": ["sensor.*goe*status", "sensor.*go_e*status", "sensor.*goe*car*"],
            },
            "wallbox": {
                "switch": ["switch.*wallbox*"],
                "current": ["number.*wallbox*current*", "number.*wallbox*amp*"],
                "power": ["sensor.*wallbox*power*"],
                "status": ["sensor.*wallbox*status*"],
            },
            "easee": {
                "switch": ["switch.*easee*charging*", "switch.*easee*toggle*"],
                "current": ["number.*easee*current*", "number.*easee*limit*"],
                "power": ["sensor.*easee*power"],
                "status": ["sensor.*easee*status"],
            },
        }
        
        if charger_type not in search_patterns:
            return None
        
        patterns = search_patterns[charger_type]
        entities = self.hass.states.async_entity_ids()
        
        found = {}
        
        # Išči switch
        for pattern in patterns["switch"]:
            matches = [e for e in entities if fnmatch.fnmatch(e.lower(), pattern.lower())]
            if matches:
                found[CONF_CHARGER_SWITCH] = matches[0]
                break
        
        # Išči current
        for pattern in patterns["current"]:
            matches = [e for e in entities if fnmatch.fnmatch(e.lower(), pattern.lower())]
            if matches:
                found[CONF_CHARGER_CURRENT] = matches[0]
                break
        
        # Išči power
        for pattern in patterns["power"]:
            matches = [e for e in entities if fnmatch.fnmatch(e.lower(), pattern.lower())]
            if matches:
                found[CONF_CHARGER_POWER] = matches[0]
                break
        
        # Išči status
        for pattern in patterns["status"]:
            matches = [e for e in entities if fnmatch.fnmatch(e.lower(), pattern.lower())]
            if matches:
                found[CONF_CHARGER_STATUS] = matches[0]
                break
        
        # Dodaj prednastavitve za enoto in status vrednosti
        presets = self._get_charger_presets(charger_type)
        found[CONF_CURRENT_UNIT] = presets["unit"]
        found[CONF_STATUS_CHARGING_VALUES] = presets["charging_values"]
        found[CONF_STATUS_CONNECTED_VALUES] = presets["connected_values"]
        
        return found if len(found) >= 4 else None  # Vsaj switch, current, power, status

    def _get_charger_presets(self, charger_type):
        """Vrne prednastavitve za različne tipe polnilnic."""
        presets = {
            "abb_terra": {
                "unit": "A",
                "charging_values": "4",  # State C2 = Charging (IEC 61851-1)
                "connected_values": "1,2,3,4,5",  # B1, B2, C1, C2, D/F
            },
            "generic": {
                "unit": "A",
                "charging_values": "charging,Charging,C",
                "connected_values": "connected,Connected,B,B1,B2",
            },
            "goe": {
                "unit": "A",
                "charging_values": "2",  # go-eCharger status kode
                "connected_values": "1,2",
            },
            "wallbox": {
                "unit": "A",
                "charging_values": "charging,Charging",
                "connected_values": "waiting,connected,paused,Waiting,Connected,Paused",
            },
            "easee": {
                "unit": "A",
                "charging_values": "charging",
                "connected_values": "ready_to_charge,awaiting_start",
            },
            "zappi": {
                "unit": "A",
                "charging_values": "EV Charging",
                "connected_values": "EV Connected,EV Charging",
            },
            "evse_din": {
                "unit": "A",
                "charging_values": "C",
                "connected_values": "B,B1,B2,C",
            },
            "openwb": {
                "unit": "A",
                "charging_values": "charging",
                "connected_values": "connected,charging",
            },
            "tesla": {
                "unit": "A",
                "charging_values": "charging",
                "connected_values": "connected,charging",
            },
            "other_custom": {
                "unit": "A",
                "charging_values": "",
                "connected_values": "",
            },
        }
        return presets.get(charger_type, presets["generic"])


class EVSCIOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    async def async_step_init(self, user_input=None):
        """Omogoči urejanje vseh nastavitev."""
        if user_input is not None:
            if user_input.get(CONF_USE_GRID_TEMPLATE) and not user_input.get(CONF_GRID_TEMPLATE):
                current_config = {**self.config_entry.data, **self.config_entry.options, **user_input}
                schema = self._get_full_schema()
                return self.async_show_form(
                    step_id="init",
                    data_schema=self.add_suggested_values_to_schema(schema, current_config),
                    errors={"base": "grid_template_required"}
                )

            # Ohranjanje opcijskih polj
            optional_fields = [CONF_SOLAR_SENSOR, CONF_EV_SOC_SENSOR, CONF_GRID_TEMPLATE]
            for key in optional_fields:
                if key not in user_input or user_input[key] in [None, "", []]:
                    user_input[key] = None

            return self.async_create_entry(title="", data=user_input)

        # Združimo trenutne nastavitve in dodamo default vrednosti za nova polja
        current_config = {**self.config_entry.data, **self.config_entry.options}
        
        # Default values for new fields if they don't exist
        if CONF_CHARGER_TYPE not in current_config:
            current_config[CONF_CHARGER_TYPE] = "generic"
        if CONF_CURRENT_UNIT not in current_config:
            current_config[CONF_CURRENT_UNIT] = "A"
        if CONF_GRID_SENSOR_INVERTED not in current_config:
            current_config[CONF_GRID_SENSOR_INVERTED] = False
        if CONF_USE_GRID_TEMPLATE not in current_config:
            current_config[CONF_USE_GRID_TEMPLATE] = False
        if CONF_STATUS_CHARGING_VALUES not in current_config:
            current_config[CONF_STATUS_CHARGING_VALUES] = "charging,Charging,C"
        if CONF_STATUS_CONNECTED_VALUES not in current_config:
            current_config[CONF_STATUS_CONNECTED_VALUES] = "connected,Connected,B,B1,B2"
        
        # Celotna shema za urejanje
        schema = self._get_full_schema()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current_config)
        )

    def _get_full_schema(self):
        """Celotna shema za urejanje nastavitev."""
        return vol.Schema({
            # Tip polnilnice
            vol.Required(CONF_CHARGER_TYPE): vol.In(CHARGER_TYPES),
            
            # Entitete polnilnice
            vol.Required(CONF_CHARGER_SWITCH): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Required(CONF_CHARGER_CURRENT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["number", "select"])
            ),
            vol.Required(CONF_CHARGER_POWER): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_CHARGER_STATUS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_EV_SOC_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_CURRENT_UNIT): vol.In(CURRENT_UNITS),
            vol.Optional(CONF_STATUS_CHARGING_VALUES): str,
            vol.Optional(CONF_STATUS_CONNECTED_VALUES): str,
            
            # Omrežje
            vol.Required(CONF_GRID_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_GRID_SENSOR_INVERTED): bool,
            vol.Optional(CONF_USE_GRID_TEMPLATE): bool,
            vol.Optional(CONF_GRID_TEMPLATE): selector.TemplateSelector(),
            vol.Optional(CONF_SOLAR_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_TARIFF_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            
            # Parametri
            vol.Required(CONF_PHASES): vol.In([1, 3]),
            vol.Required(CONF_MAX_FUSE): vol.All(int, vol.Range(min=6, max=100)),
            vol.Required(CONF_BUFFER): vol.All(int, vol.Range(min=0, max=2000)),
            vol.Required(CONF_CONTROL_INTERVAL): vol.All(int, vol.Range(min=5, max=300)),
            vol.Required(CONF_AUTO_MODE): selector.SelectSelector(
                selector.SelectSelectorConfig(options=AUTO_MODES, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_RESET_ON_UNPLUG): bool,
            
            # Tarifni bloki
            vol.Required(CONF_LIMIT_BLOCK_1): vol.All(int, vol.Range(min=1000, max=50000)),
            vol.Required(CONF_LIMIT_BLOCK_2): vol.All(int, vol.Range(min=1000, max=50000)),
            vol.Required(CONF_LIMIT_BLOCK_3): vol.All(int, vol.Range(min=1000, max=50000)),
            vol.Required(CONF_LIMIT_BLOCK_4): vol.All(int, vol.Range(min=1000, max=50000)),
            vol.Required(CONF_LIMIT_BLOCK_5): vol.All(int, vol.Range(min=1000, max=50000)),
        })
