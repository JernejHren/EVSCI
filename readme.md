# EVSCI - EV Smart Charging Integration 🍌⚡️

**EVSCI** is an advanced Energy Management System (EMS) for Home Assistant, designed to optimize electric vehicle charging. It dynamically adjusts charging power based on your home's grid usage, solar production, and specific network tariff blocks, preventing main fuse trips and optimizing costs.

## ✨ Key Features

*   **🛡️ Main Fuse Protection:** Actively monitors total house consumption. If you turn on the oven or heat pump, EVSCI immediately lowers the EV charging current to prevent the main fuse from tripping.
*   **📉 Network Tariff Blocks (Slovenia & others):** Specifically designed to respect the power limits of the current tariff block (e.g., the new NMPT system in Slovenia).
*   **☀️ Solar Charging (PV):** Modes to charge exclusively from excess solar energy or mix grid/solar.
*   **🤖 Automation & UX:**
    *   **Auto-Start:** Automatically detects when the car is plugged in and switches to your preferred mode.
    *   **Session Persistence:** Uses 0A (Pause) instead of stopping the session when power is low, ensuring charging resumes automatically.
    *   **Soft Ramp-up:** Increases current gradually to be gentle on the grid and battery.
*   **🔋 Target SoC:** Stops charging when the vehicle battery reaches a specific percentage (requires vehicle integration).

---

## ⚠️ Important: Tariff Sensor Requirement

This integration relies on knowing the current **Tariff Block (1-5)** to determine the allowed power limit for that specific time of day. This is mandatory during setup.

### 🇸🇮 For Users in Slovenia
It is highly recommended to use the **[Network Tariff (NMPT)](https://github.com/frlequ/home-assistant-network-tariff)** integration by *frlequ*. It automatically provides the correct block (1-5) for the Slovenian grid.
*   Select the entity provided by this integration (e.g., `sensor.network_tariff_current_block`) during setup.

### 🌍 For International Users / Single Tariff
If you live in a country with a single power limit (no complex time blocks), you **must create a template sensor** that always returns `1`.

Add this to your `configuration.yaml`:

```yaml
template:
  - sensor:
      - name: "EVSCI Dummy Tariff"
        state: "1"

Then select sensor.evsci_dummy_tariff during installation.

    In the configuration settings, set Limit Block 1 to your home's main power limit (e.g., 11000 W).

    You can ignore limits for Blocks 2-5.

🕒 For Users with simple Day/Night Tariffs

You can create a template sensor that returns 1 during the day and 2 during the night, and set different power limits for Block 1 and Block 2 in the EVSCI configuration.
🚀 Charging Modes

    OFF: Charging is disabled.

    Dynamic: The smartest mode. Charges as fast as possible but strictly respects the current Tariff Block limit to avoid penalty fees.

    PV Only: Charges only using excess solar energy. If excess power drops below 6A, charging pauses (0A).

        Note: Works independently of tariff blocks (uses available solar).

    Min + PV: Always charges at minimum power (6A) from the grid to ensure progress, but adds excess solar power on top when available.

    Max Power: Charges at the maximum speed allowed by your Main Fuse.

        Warning: This ignores Tariff Block limits and might incur grid fees, but ensures the fastest charge without tripping the physical fuse.

    Schedule: Works like Dynamic, but only within the time window you define (e.g., 22:00 - 06:00). Outside this window, charging is paused (0A).

⚙️ Installation
Via HACS (Recommended)

    Open HACS -> Integrations.

    Add this repository as a Custom Repository.

    Search for "EV Smart Charging Integration" and install.

    Restart Home Assistant.

Manual Installation

    Copy the custom_components/evsci folder into your Home Assistant's config/custom_components/ directory.

    Restart Home Assistant.

🔧 Configuration

Go to Settings -> Devices & Services -> Add Integration -> EV Smart Charging Integration.
Required Sensors

To work correctly, EVSCI needs to "see" your house:

    Grid Power Sensor (W): Measures power at your main meter.

        Positive value: Importing from grid (Consumption).

        Negative value: Exporting to grid (Solar surplus).

    Charger Power Sensor (W): Measures how much power the EV is currently drawing.

    Charger Switch: The entity to turn the charger ON/OFF.

    Charger Current: The entity to set the charging Amps (A).

    Charger Status: A sensor indicating status (e.g., "Charging", "Idle", "Connected") used for Auto-Start detection.

    Tariff Sensor: (See section above).

Optional Sensors

    Solar Power Sensor (W): Used for display/stats.

    EV Battery Sensor (%): Used for the "Target Battery Limit" feature.

📊 Lovelace Dashboard Card

To get the full control panel (Mode selection, Gauges, Slider, Stats), use this YAML code in your Dashboard:
code Yaml

    
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
      - entity: number.target_battery_limit
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

  
