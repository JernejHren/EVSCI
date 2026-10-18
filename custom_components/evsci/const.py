"""Konstante za EVSCI integracijo."""

DOMAIN = "evsci"

# Konfiguracijski ključi - Senzorji
CONF_GRID_SENSOR = "grid_sensor"
# Legacy (switch-based control)
CONF_CHARGER_SWITCH = "charger_switch"
CONF_CHARGER_START_BUTTON = "charger_start_button"
CONF_CHARGER_STOP_BUTTON = "charger_stop_button"
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
CONF_VOLTAGE = "voltage"
CONF_MIN_CURRENT = "min_current"
CONF_MAX_CURRENT = "max_current"

# Zaščita varovalke
CONF_FUSE_PROTECTION = "fuse_protection"
FUSE_PROTECTION_TOTAL = "total"          # po skupni porabi hiše (privzeto)
FUSE_PROTECTION_PER_PHASE = "per_phase"  # po najšibkejši fazi (3f)
FUSE_PROTECTION_MODES = [FUSE_PROTECTION_TOTAL, FUSE_PROTECTION_PER_PHASE]
CONF_PHASE_SENSOR_L1 = "phase_sensor_l1"
CONF_PHASE_SENSOR_L2 = "phase_sensor_l2"
CONF_PHASE_SENSOR_L3 = "phase_sensor_l3"
PHASE_SENSOR_KEYS = [CONF_PHASE_SENSOR_L1, CONF_PHASE_SENSOR_L2, CONF_PHASE_SENSOR_L3]
CONF_CHARGER_PHASE = "charger_phase"     # faza enofaznega polnilnika
CHARGER_PHASES = ["L1", "L2", "L3"]

# Statusi polnilnika, ki pomenijo "kabel ni priklopljen" (ločeni z vejico)
CONF_IDLE_STATUSES = "idle_statuses"
DEFAULT_IDLE_STATUSES = "0, State A - Idle, False, No cable plugged"

# Privzete vrednosti
DEFAULT_VOLTAGE = 230
DEFAULT_MIN_CURRENT = 6
DEFAULT_MAX_CURRENT = 32

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
MODE_LOW_TARIFF = "Low Tariff"
MODE_NO_CHANGE = "Don't Change"

MODES = [MODE_OFF, MODE_PV_ONLY, MODE_MIN_PV, MODE_DYNAMIC, MODE_MAX_POWER, MODE_SCHEDULE, MODE_LOW_TARIFF]

# Način Low Tariff polni, ko je tarifni blok >= izbranega (višji blok = nižja cena)
DEFAULT_LOW_TARIFF_BLOCK = 3
AUTO_MODES = [MODE_NO_CHANGE] + MODES
