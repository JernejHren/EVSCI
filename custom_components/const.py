"""Konstante za EVSCI integracijo."""

DOMAIN = "evsci"

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
CONF_CONTROL_INTERVAL = "control_interval"  # <--- NOVO

# Limiti za bloke (W)
CONF_LIMIT_BLOCK_1 = "limit_block_1"
CONF_LIMIT_BLOCK_2 = "limit_block_2"
CONF_LIMIT_BLOCK_3 = "limit_block_3"
CONF_LIMIT_BLOCK_4 = "limit_block_4"
CONF_LIMIT_BLOCK_5 = "limit_block_5"

# Načini delovanja
MODE_OFF = "OFF"
MODE_PV_ONLY = "PV Only"
MODE_MIN_PV = "Min + PV"
MODE_DYNAMIC = "Dynamic"
MODE_MAX_POWER = "Max Power"
MODE_SCHEDULE = "Schedule"
MODE_NO_CHANGE = "Don't Change"

MODES = [MODE_OFF, MODE_PV_ONLY, MODE_MIN_PV, MODE_DYNAMIC, MODE_MAX_POWER, MODE_SCHEDULE]
AUTO_MODES = [MODE_NO_CHANGE] + MODES
