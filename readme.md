# EVSCI - EV Smart Charging Integration ⚡️

**EVSCI** is an advanced Energy Management System (EMS) for Home Assistant, specifically designed to optimize electric vehicle charging at home.

It dynamically adjusts the charging current based on your home's total grid consumption, solar production, and specific **Network Tariff Blocks**, preventing main fuse trips and optimizing charging costs.


## ✨ Key Features

*   **🛡️ Main Fuse Protection:** Actively monitors total house consumption. If you turn on high-load appliances (oven, heat pump), EVSCI immediately lowers the EV charging current to prevent the main fuse from tripping.
*   **🔌 Per-phase protection (3-phase):** Optionally protect the fuse of each phase instead of the total consumption. EVSCI then limits the charging current by the most loaded phase.
*   **📉 Network Tariff Blocks:** Specifically designed to respect the power limits of the current tariff block (e.g., the NMPT system in Slovenia). It ensures you stay within the agreed power profile to avoid penalty fees.
*   **☀️ Solar Charging (PV):** Intelligent modes to charge using only excess solar energy or a mix of grid and solar.
*   **🤖 Smart Automation:**
    *   **Auto-Start:** Automatically detects when the car is plugged in and switches to your preferred default mode.
    *   **Session Persistence:** Instead of stopping the session when power is low, it pauses charging (0A), allowing it to resume automatically without re-authorization.
    *   **Full-power start:** Charging starts right away at the highest current the available power allows (no slow ramp-up at start). A short grace period after start prevents false overload detection while the charger's power sensor catches up.
    *   **Smooth PV tracking:** In the PV modes, the current is adjusted in 2 A steps during charging so it doesn't jump up and down, but it still decreases immediately in case of overload.
*   **🔋 Target SoC Limit:** Stops charging when the vehicle battery reaches a specific percentage (requires a vehicle integration in Home Assistant).

---

## 🏷️ Tariff Sensor (optional)

A **Tariff Block sensor** (integer 1-5) lets EVSCI apply a different power limit for each time-of-day block. It is **optional**.

### 🇸🇮 For Users in Slovenia
It is highly recommended to use the **[Network Tariff (NMPT)](https://github.com/frlequ/home-assistant-network-tariff)** integration. It automatically provides the correct block (1-5) for the Slovenian grid.
*   Select the entity provided by this integration (e.g., `sensor.network_tariff_current_block`) during setup.

### 🌍 For International Users / Single Tariff
Leave the **Tariff Block Sensor** field empty. EVSCI then always uses block 1.
*   In the configuration settings, set **Limit Block 1** to your home's main power limit (e.g., 11000 W).
*   You can ignore limits for Blocks 2-5.

## 🚀 Charging Modes

*   **OFF:** Charging is disabled.
*   **Dynamic:** The smartest mode. Charges as fast as possible but **strictly respects the current Tariff Block limit** to avoid penalty fees.
*   **PV Only:** Charges **only** using excess solar energy.
    *   Starts when excess power covers the minimum current (6 A by default) plus the safety buffer, and then starts directly at the highest current the excess allows.
    *   Adjusts the current in 2 A steps during charging.
    *   Pauses (0A) if clouds appear or house consumption rises.
*   **Min + PV:** Always charges at minimum power (6A) from the grid to ensure progress, but adds excess solar power on top when available.
*   **Max Power:** Charges at the maximum speed allowed by your **Main Fuse**.
    *   *Warning:* This ignores Tariff Block limits and might incur grid fees, but ensures the fastest charge without tripping the physical fuse.
*   **Schedule:** Works like *Dynamic*, but only within the time window you define (e.g., 22:00 - 06:00). Outside this window, charging is paused (0A).

---

## ⚙️ Installation

### Via HACS (Recommended)
1.  Open **HACS** -> **Integrations**.
2.  Click the three dots in the top right corner -> **Custom repositories**.
3.  Paste the URL of this repository.
4.  Category: **Integration**.
5.  Click **Add**, then search for "EV Smart Charging Integration" and install.
6.  **Restart Home Assistant**.

### Manual Installation
1.  Download the `evsci.zip` file (or clone the repo).
2.  Copy the `custom_components/evsci` folder into your Home Assistant's `config/custom_components/` directory.
3.  **Restart Home Assistant**.

---

## 🔧 Configuration

Go to **Settings** -> **Devices & Services** -> **Add Integration** -> **EV Smart Charging Integration**.

### Required Sensors
To work correctly, EVSCI needs to "see" your house:

*   **Grid Power Sensor (W):** Measures power at your main meter (e.g., Shelly EM, Smart Meter).
    *   *Positive value (+):* Importing from grid (Consumption).
    *   *Negative value (-):* Exporting to grid (Solar surplus).
*   **Charger Power Sensor (W):** Measures how much power the EV is currently drawing.
*   **Charger Start / Stop Buttons:** The `button` entities that start and stop a charging session.
*   **Charger Current:** The entity to set the charging Amps (A).
*   **Charger Status:** A sensor indicating status (e.g., "Charging", "Idle", "Connected", "B") used for Auto-Start detection.
*   **Tariff Sensor (optional):** See the section above.

### Parameters
*   **Phases:** 1 or 3 (depends on your installation).
*   **Main Fuse (A):** The physical limit of your main house fuse (e.g., 20A or 25A).
*   **Main Fuse Protection:** *Total house power* (default) or *Per phase* (3-phase only).
    *   *Per phase* asks for the current sensors (A) of L1, L2 and L3 at your grid connection point. Sensors that report a sign (import +, export -) work best; a sensor reporting only the magnitude is treated as import (the safe side).
    *   With a single-phase charger on a 3-phase house you also select the phase it is connected to. A 3-phase charger loads all three phases equally.
    *   If a phase sensor becomes unavailable or stale, charging pauses until it returns.
    *   Tariff block limits and PV surplus still use the total power from the Grid Power Sensor.
*   **Safety Buffer (W):** Power reserve to prevent tripping (recommended: 200-500W).
*   **Supply Voltage (V):** Phase voltage used to convert amps to watts (default 230 V).
*   **Charger Minimum / Maximum Current (A):** The current range your charger supports (defaults 6 A and 32 A).
*   **Control Interval:** How often the current may be changed during charging (default 30s). *Note: Decreasing current on overload happens immediately for safety.*
*   **Solar surplus** is derived from the Grid Power Sensor (export = surplus), so no separate solar sensor is needed.

---

## 📊 Dashboard Card
To get the full control panel (Mode selection, Gauges, Slider, Stats), use this YAML code in your Dashboard:
code Yaml

```yaml    
type: vertical-stack
cards:
  - type: tile
    entity: select.charging_mode
    name: Charging Mode
    icon: mdi:ev-station
    color: blue
    vertical: false
    features:
      - type: select-options
    features_position: bottom
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.monitored_grid_power
        name: Grid Power
        unit: W
        min: -10000
        max: 13000
        needle: true
        severity:
          green: -10000
          yellow: 4000
          red: 12000 # Set this to your Main Fuse limit
      - type: gauge
        entity: sensor.target_current
        name: Target Amps
        unit: A
        min: 0
        max: 32
        needle: true
        severity:
          green: 6
          yellow: 16
          red: 25
  - type: entities
    entities:
      - entity: number.target_soc
        name: Target Battery (%)
        icon: mdi:battery-charging-high
  - type: conditional
    conditions:
      - entity: select.charging_mode
        state: "Schedule"
    card:
      type: entities
      title: Schedule Settings
      entities:
        - entity: time.schedule_start
          name: Start Time
        - entity: time.schedule_end
          name: End Time
  - type: entities
    title: Session Statistics
    entities:
      - entity: sensor.session_energy_total
        name: Session Energy
        icon: mdi:lightning-bolt
      - entity: sensor.session_energy_solar
        name: Solar Part
        icon: mdi:solar-power
      - entity: sensor.session_energy_grid
        name: Grid Part
        icon: mdi:transmission-tower
      - entity: sensor.monitored_tariff_block
        name: Current Tariff Block
        icon: mdi:cash-multiple
```
  

---

## 🧪 Development

The charging decisions live in `custom_components/evsci/logic.py` as pure functions (no Home Assistant needed), so they can be unit tested:

```bash
pip install -r requirements_test.txt
python -m pytest tests
```

---

## 📄 License

Apache License 2.0, see [LICENSE](LICENSE).
