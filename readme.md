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
