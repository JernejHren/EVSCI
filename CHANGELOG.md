# Changelog

All notable changes to EVSCI since 0.1.3.

## [0.2.0] - 2026-04-06
- Configuration now asks for dedicated Charger Start and Charger Stop buttons (with legacy switch support still available) and the translations were updated so both languages describe the new controls.
- Target SoC is exposed as a new `number` entity that restores its last value, giving a quick UI control for the stop percentage while letting EVSCI remember it across restarts.
- Mode select plus schedule start/end times now restore their last saved state, keeping the previously chosen mode and schedule window active after HA reboots.
- Charging session tracking and actuation got overhauled: the coordinator now monitors actual power to recognize when a charge session is running, tracks plug/unplug events, enforces PV-only pause-and-resume hysteresis, and toggles the charger through the new button services (or the legacy switch) so that start/stop happens reliably.
