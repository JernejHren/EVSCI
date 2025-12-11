# EVSCI - EV Smart Charging Integration 🍌⚡️

**EVSCI** is an advanced Energy Management System (EMS) for Home Assistant, specifically designed to optimize electric vehicle charging at home.

It dynamically adjusts the charging current based on your home's total grid consumption, solar production, and specific **Network Tariff Blocks**, preventing main fuse trips and optimizing charging costs.

![EVSCI Logo](https://github.com/yourusername/evsci/blob/main/logo.png?raw=true)
*(Note: If you don't have a logo image yet, remove the line above)*

## ✨ Key Features

*   **🛡️ Main Fuse Protection:** Actively monitors total house consumption. If you turn on high-load appliances (oven, heat pump), EVSCI immediately lowers the EV charging current to prevent the main fuse from tripping.
*   **📉 Network Tariff Blocks:** Specifically designed to respect the power limits of the current tariff block (e.g., the NMPT system in Slovenia). It ensures you stay within the agreed power profile to avoid penalty fees.
*   **☀️ Solar Charging (PV):** Intelligent modes to charge using only excess solar energy or a mix of grid and solar.
*   **🤖 Smart Automation:**
    *   **Auto-Start:** Automatically detects when the car is plugged in and switches to your preferred default mode.
    *   **Session Persistence:** Instead of stopping the session when power is low, it pauses charging (0A), allowing it to resume automatically without re-authorization.
    *   **Soft Ramp-up:** Increases current gradually to be gentle on the grid and battery, but decreases immediately in case of overload.
*   **🔋 Target SoC Limit:** Stops charging when the vehicle battery reaches a specific percentage (requires a vehicle integration in Home Assistant).

---

## ⚠️ Prerequisite: Tariff Sensor

This integration **requires** a sensor that reports the current **Tariff Block (as an integer 1-5)**. This is used to determine the power limit for the current time of day.

### 🇸🇮 For Users in Slovenia
It is highly recommended to use the **[Network Tariff (NMPT)](https://github.com/frlequ/home-assistant-network-tariff)** integration. It automatically provides the correct block (1-5) for the Slovenian grid.
*   Select the entity provided by this integration (e.g., `sensor.network_tariff_current_block`) during setup.

### 🌍 For International Users / Single Tariff
If you live in a country with a single power limit (no complex time blocks), you **must create a template sensor** that always returns `1`.

Add this to your `configuration.yaml` and restart Home Assistant:

```yaml
template:
  - sensor:
      - name: "EVSCI Dummy Tariff"
        state: "1"
```
