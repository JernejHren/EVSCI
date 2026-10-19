# EVSCI - EV Smart Charging Integration ⚡️

**EVSCI** is an advanced Energy Management System (EMS) for Home Assistant, specifically designed to optimize electric vehicle charging at home.

It dynamically adjusts the charging current based on your home's total grid consumption, solar production, and specific **Network Tariff Blocks**, preventing main fuse trips and optimizing charging costs.


## ✨ Key Features

*   **🛡️ Main Fuse Protection:** Actively monitors total house consumption. If you turn on high-load appliances (oven, heat pump), EVSCI immediately lowers the EV charging current to prevent the main fuse from tripping.
*   **🔌 Per-phase protection (3-phase):** Optionally protect each phase in addition to the total consumption. The total limit always applies, and if one phase gets overloaded (e.g. by extra appliances on it), the charging current is lowered on all phases.
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
*   **Low Tariff:** Works like *Dynamic* (it respects the limit of the current tariff block), but charges only while the tariff block is the selected one or a cheaper one. Set the block with the **Low Tariff Block** number entity (1-5, default 3). A higher block number means a cheaper tariff, so with 3 selected it charges in blocks 3, 4 and 5 and pauses (0A) in blocks 2 and 1. Requires the Tariff Sensor; without it this mode never charges.

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
*   **Charger Start / Stop:** Either the two `button` entities that start and stop a charging session, or a single `switch` entity that does both.
*   **Charger Current:** The entity to set the charging Amps (A).
*   **Charger Status:** A sensor indicating status (e.g., "Charging", "Idle", "Connected", "B") used for Auto-Start detection.
    *   **Statuses meaning "cable not plugged in":** Comma separated list of status values that mean no car is connected (not case sensitive). Default: `0, State A - Idle, False, No cable plugged` (ABB Terra AC). Any other status is treated as plugged in; `unavailable` and `unknown` always count as not plugged in.
*   **Tariff Sensor (optional):** See the section above.

### Parameters
*   **Phases:** 1 or 3 (depends on your installation).
*   **Main Fuse (A):** The physical limit of your main house fuse (e.g., 20A or 25A).
*   **Main Fuse Protection:** *Total house power only* (default) or *Total house power and each phase* (3-phase only). In the second mode both limits apply at the same time and the stricter one wins.
    *   The second mode asks for the current sensors (A) of L1, L2 and L3 at your grid connection point. Sensors that report a sign (import +, export -) work best; a sensor reporting only the magnitude is treated as import (the safe side).
    *   With a single-phase charger on a 3-phase house you also select the phase it is connected to. A 3-phase charger loads all three phases equally.
    *   If a phase sensor becomes unavailable or stale, charging pauses until it returns.
    *   The total limit (main fuse, or the tariff block in Dynamic/Schedule/Low Tariff) and PV surplus always use the total power from the Grid Power Sensor.
*   **Safety Buffer (W):** Power reserve to prevent tripping (recommended: 200-500W).
*   **Supply Voltage (V):** Phase voltage used to convert amps to watts (default 230 V).
*   **Charger Minimum / Maximum Current (A):** The current range your charger supports (defaults 6 A and 32 A).
*   **Control Interval:** How often the current may be changed during charging (default 30s). *Note: Decreasing current on overload happens immediately for safety.*
*   **Solar surplus** is derived from the Grid Power Sensor (export = surplus), so no separate solar sensor is needed.

---

## 🔄 How It Works and How Data Is Updated

EVSCI does not talk to your charger or meter directly. It only reads the state of Home Assistant entities and sends commands to other Home Assistant entities, so the update rate is set by how often your own sensors report.

*   **Calculation cycle:** every 5 seconds EVSCI reads the entities, makes a decision and, if needed, sends a command (`number.set_value` for the current, a button press or switch for start/stop). The integration type is *calculated*, there is no polling of a device or cloud.
*   **Changing the current:** while charging, the current is changed at most once per *Control Interval* (default 30 s). It rises by at most 2 A per change. A **decrease because of an overload is immediate**.
*   **Stale data:** if the Grid Power Sensor (or a phase current sensor) has not reported for more than 60 seconds, or is unavailable, EVSCI pauses charging (0 A) until it reports again. A Repair appears after 5 minutes.
*   **After a start:** for 15 seconds EVSCI estimates the charger power from the commanded current while the charger's own power sensor catches up.
*   **Energy counters:** the session and lifetime energy sensors add up the charger power every cycle. The solar/grid split is an estimate derived from the net grid power: the part of the charger power that is not imported from the grid is counted as solar energy.

---

## 🔌 Supported Devices

EVSCI is developed and used with the **ABB Terra AC** wallbox over Modbus. Nothing else has been tested.

In principle any charger works that shows up in Home Assistant with:

*   a `number` entity that sets the charging current in amps,
*   a `sensor` with the charger power in watts,
*   a `sensor` with the charger status (used to detect that a car is plugged in; see *Statuses meaning "cable not plugged in"*),
*   a start and a stop `button`, or one `switch` that starts and stops charging.

If you try another charger, please report how it went in the [issue tracker](https://github.com/JernejHren/EVSCI/issues).

---

## 🧩 Supported Functions

All entities belong to one device, *EV Smart Charging*. The integration has no services (actions) of its own.

| Entity | Type | What it does |
|---|---|---|
| Charging Mode | `select` | OFF, PV Only, Min + PV, Dynamic, Max Power, Schedule, Low Tariff. The selection is restored after a restart. |
| Target SoC | `number` (configuration) | Stops charging at this battery level (needs the EV Battery Sensor). 100 means no limit. |
| Low Tariff Block | `number` (configuration) | Block for the Low Tariff mode, 1-5, default 3. |
| Schedule Start / End | `time` (configuration) | Time window of the Schedule mode, default 22:00-06:00. |
| Target Current | `sensor` (A) | The current EVSCI wants the charger to use. |
| Monitored Tariff Block | `sensor` (diagnostic) | Tariff block that EVSCI is using. |
| Monitored Grid Power | `sensor` (diagnostic, disabled by default) | Copy of your grid power sensor. |
| Session Energy Total / Solar / Grid | `sensor` (kWh) | Energy of the current session, reset when a car is plugged in. |
| Lifetime Energy Total / Solar / Grid | `sensor` (kWh) | Total energy, kept across restarts (suitable for the Energy dashboard). |

Other functions: **Reconfigure** (change the setup without removing it), **Download diagnostics** (device page, three dots menu), and **Repairs** that appear when a sensor is unavailable for 5 minutes or when the Low Tariff mode is selected without a tariff sensor.

---

## 💡 Use Cases

*   **Avoid a tripped fuse or network penalty fees (Slovenia):** use *Dynamic* with the NMPT tariff sensor and set a limit for every block. EVSCI charges as fast as the current block allows and lowers the current when other appliances start.
*   **Charge only when electricity is cheap:** use *Low Tariff* and set *Low Tariff Block* to the cheapest blocks you accept. With 3 selected it charges in blocks 3, 4 and 5 and pauses in blocks 2 and 1.
*   **Use your own solar energy:** use *PV Only* (surplus only) or *Min + PV* (minimum from the grid, plus the surplus).
*   **A 3-phase house where one phase carries other loads:** switch *Main Fuse Protection* to *Total house power and each phase*, so the busiest phase limits the charging current.
*   **Quick top-up:** use *Max Power* for the fastest charge the main fuse allows (it ignores tariff block limits).

---

## 🤖 Automation Examples

The examples use the entity IDs of an existing installation. On a new installation use the IDs of your device (for example `select.ev_smart_charging_charging_mode`).

**Charge at night in the cheap tariff:**

```yaml
automation:
  - alias: "EV: night charging in cheap tariff"
    triggers:
      - trigger: time
        at: "21:00:00"
    actions:
      - action: select.select_option
        target:
          entity_id: select.charging_mode
        data:
          option: "Low Tariff"
```

**Solar charging during the day, cheap tariff otherwise:**

```yaml
automation:
  - alias: "EV: solar when the sun is high"
    triggers:
      - trigger: numeric_state
        entity_id: sun.sun
        attribute: elevation
        above: 15
    actions:
      - action: select.select_option
        target:
          entity_id: select.charging_mode
        data:
          option: "PV Only"
  - alias: "EV: cheap tariff when the sun is low"
    triggers:
      - trigger: numeric_state
        entity_id: sun.sun
        attribute: elevation
        below: 5
    actions:
      - action: select.select_option
        target:
          entity_id: select.charging_mode
        data:
          option: "Low Tariff"
```

**One hour of full power, then back to Dynamic:**

```yaml
script:
  ev_boost:
    alias: "EV: boost for one hour"
    sequence:
      - action: select.select_option
        target:
          entity_id: select.charging_mode
        data:
          option: "Max Power"
      - delay: "01:00:00"
      - action: select.select_option
        target:
          entity_id: select.charging_mode
        data:
          option: "Dynamic"
```

(The delay is lost if Home Assistant restarts during the hour.)

---

## 📊 Dashboard Card

> **Entity IDs:** The examples below use short IDs such as `select.charging_mode`. In the upcoming release all entities belong to the device *EV Smart Charging*. Installations that were set up before keep their old IDs. On a new installation the IDs start with the device name (for example `select.ev_smart_charging_charging_mode`), so adjust the card to your actual entity IDs.
>
> The sensor *Monitored Grid Power* is a copy of your own grid sensor, so it is a diagnostic entity and disabled by default on new installations. Enable it in the device page if you want it on the card, or point the card at your own grid sensor. The settings entities (Target SoC, Low Tariff Block, Schedule Start/End) are in the *Configuration* section of the device.

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
        state: "Low Tariff"
    card:
      type: entities
      entities:
        - entity: number.low_tariff_block
          name: Charge in this tariff block or cheaper
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

## ⚠️ Known Limitations

*   **One charger per setup.** A second entry for the same charger is refused. Two entries for two chargers on the same grid connection do **not** share the fuse or tariff budget: each one assumes it can use all of it, so do not do that.
*   **Only tested with an ABB Terra AC** and, for now, with unit tests and simulations rather than a wide range of real installations.
*   **The Grid Power Sensor must measure at the connection point** and include the charger (positive = import, negative = export). A sensor that does not include the charger, or with a different sign, gives wrong results.
*   **Tariff block numbers:** the Low Tariff mode assumes a higher block number means a cheaper tariff (as in Slovenia).
*   **Phase current sensors:** signed values (import +, export -) work best. A sensor that reports only the magnitude is treated as import, which is the safe side but can limit charging more than needed while exporting.
*   **Reaction time:** the current rises by at most 2 A per *Control Interval*, so reaching a high current from a low one takes a while. Only overload decreases are immediate.
*   **Removing the integration does not stop a running charge.** Set the mode to OFF first.
*   **Cable detection** depends on the charger status values. Set *Statuses meaning "cable not plugged in"* if yours are different.

---

## 🛠️ Troubleshooting

First check the **Repairs** page and, if needed, enable debug logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.evsci: debug
```

You can also download the diagnostics from the device page and attach them to an issue.

| Problem | What to check |
|---|---|
| Charging does not start | Mode is not OFF; *Target SoC* is not reached; the Grid Power Sensor reports (not older than 60 s); there is enough room below the limit. The minimum is the minimum current x voltage x phases (6 A on 3 phases = about 4.1 kW) plus the Safety Buffer. |
| *PV Only* does not start | The solar surplus (export) must cover the minimum current plus the Safety Buffer. |
| *Low Tariff* or *Dynamic* does not behave as expected | The Tariff Sensor must be set and give a value from 1 to 5. Without it *Low Tariff* never charges, and *Dynamic* and *Schedule* use block 1. Check the limit of the current block. |
| *Schedule* does not charge | The current time must be inside *Schedule Start* and *Schedule End*. |
| Charging pauses (0 A) | A sensor is unavailable or stale (see Repairs), the limit is reached, or a phase is overloaded in the per-phase mode. |
| The mode is not set when a car is plugged in | Check *Default Mode on Plug-in* and the status values: the plugged-in status must not be in *Statuses meaning "cable not plugged in"*. |
| "Entity not found" in the setup form | The entity does not exist or is disabled. Enable it first. |
| The integration "retries" after a restart | One of the Grid Power, Charger Current or Charger Power entities does not exist yet. EVSCI waits until it does. |
| Entity IDs look different from the README | New installations use the device name as a prefix. See the note at the dashboard card. |

---

## 🗑️ Removing the Integration

1.  Set **Charging Mode** to **OFF** so the running session is stopped (removing the integration does not stop a charge in progress).
2.  Go to **Settings** -> **Devices & Services** -> **EV Smart Charging Integration**, open the three dots menu of the entry and click **Delete**. The device, its entities and its Repairs are removed.
3.  Optional: remove the integration files. With HACS use *Remove* in the HACS entry; for a manual installation delete `config/custom_components/evsci` and restart Home Assistant.

Long-term statistics of the energy sensors stay in the Home Assistant database until you delete them.

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
