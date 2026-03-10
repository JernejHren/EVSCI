"""Konstante za EVSCI integracijo."""

DOMAIN = "evsci"

# === ORIGINAL CONFIGURATION KEYS ===

# Konfiguracijski ključi - Senzorji
CONF_GRID_SENSOR = "grid_sensor"
CONF_SOLAR_SENSOR = "solar_sensor"
CONF_CHARGER_SWITCH = "charger_switch"
CONF_CHARGER_CURRENT = "charger_current"
CONF_CHARGER_POWER = "charger_power"
CONF_CHARGER_STATUS = "charger_status"
CONF_EV_SOC_SENSOR = "ev_soc_sensor"
CONF_TARIFF_SENSOR = "tariff_sensor"

# Konfiguracijski ključi - Parametri
CONF_PHASES = "phases"
CONF_MAX_FUSE = "max_fuse"
CONF_BUFFER = "buffer"
CONF_AUTO_MODE = "auto_mode"
CONF_RESET_ON_UNPLUG = "reset_on_unplug"
CONF_CONTROL_INTERVAL = "control_interval"

# Limiti za bloke (W)
CONF_LIMIT_BLOCK_1 = "limit_block_1"
CONF_LIMIT_BLOCK_2 = "limit_block_2"
CONF_LIMIT_BLOCK_3 = "limit_block_3"
CONF_LIMIT_BLOCK_4 = "limit_block_4"
CONF_LIMIT_BLOCK_5 = "limit_block_5"

# === NEW CONFIGURATION KEYS (for universal compatibility) ===

# Charger Configuration
CONF_CHARGER_TYPE = "charger_type"
CONF_CURRENT_UNIT = "current_unit"
CONF_STATUS_CHARGING_VALUES = "status_charging_values"
CONF_STATUS_CONNECTED_VALUES = "status_connected_values"

# Current unit options
CURRENT_UNITS = ["A", "mA", "W"]

# Grid Configuration
CONF_GRID_SENSOR_INVERTED = "grid_sensor_inverted"
CONF_USE_GRID_TEMPLATE = "use_grid_template"
CONF_GRID_TEMPLATE = "grid_template"

# === CHARGING MODES ===

MODE_OFF = "OFF"
MODE_PV_ONLY = "PV Only"
MODE_MIN_PV = "Min + PV"
MODE_DYNAMIC = "Dynamic"
MODE_MAX_POWER = "Max Power"
MODE_SCHEDULE = "Schedule"
MODE_NO_CHANGE = "No Change"  # Original value for backward compatibility

# Lista načinov za select entity
MODES = [
    MODE_OFF,
    MODE_DYNAMIC,
    MODE_PV_ONLY,
    MODE_MIN_PV,
    MODE_MAX_POWER,
    MODE_SCHEDULE,
]

# Lista načinov za auto-start (vključno z "Don't Change")
AUTO_MODES = [MODE_NO_CHANGE] + MODES

# === CHARGER TYPE PRESETS ===
CHARGER_PRESETS = {
    "abb_terra": {
        "name": "ABB Terra AC",
        "description": "ABB Terra AC (Modbus TCP)",
    },
    "generic": {
        "name": "Generic EVSE",
        "description": "Standard polnilnica s switch + number",
    },
    "goe": {
        "name": "go-eCharger",
        "description": "go-eCharger HOME+, Gemini flex, HOMEfix",
    },
    "wallbox": {
        "name": "Wallbox",
        "description": "Wallbox Pulsar, Commander, Copper",
    },
    "easee": {
        "name": "Easee",
        "description": "Easee Home, Easee Charge",
    },
    "zappi": {
        "name": "myenergi Zappi",
        "description": "Zappi v1/v2",
    },
    "evse_din": {
        "name": "EVSE DIN",
        "description": "DIN rail polnilnice z Modbus",
    },
    "openwb": {
        "name": "OpenWB",
        "description": "OpenWB Series 1/2",
    },
    "tesla": {
        "name": "Tesla Wall Connector",
        "description": "Tesla Wall Connector Gen 2/3",
    },
    "other_custom": {
        "name": "Drugo / Po meri",
        "description": "Ročna konfiguracija za nestandardne polnilnice",
    },
}
