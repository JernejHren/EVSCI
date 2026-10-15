# Changelog

All notable changes to EVSCI since 0.1.3.

## [Unreleased]

### Changed
- Charging now starts right away at the highest current the available power allows. The slow ramp-up at start (6 A, then +2 A every control interval) is gone in all modes. In the PV modes the current is still adjusted in 2 A steps during charging to avoid jumping up and down.
- A 15 s grace period after start (or resume from pause) estimates the charger power from the commanded current while the charger's power sensor catches up. This prevents false overload detection and a false loss of PV surplus right after start.
- Charger minimum current, maximum current and supply voltage are now settings (defaults 6 A, 32 A, 230 V) instead of hardcoded values.
- The Tariff Block Sensor is now optional. Without it EVSCI always uses limit block 1.

### Removed
- The optional solar power sensor (setup field and `Monitored Solar Power` entity). It was never used by the control logic, solar surplus is derived from the grid sensor. A leftover `solar_sensor` key in existing entries is ignored.

### Fixed
- Stale grid data detection now uses `last_reported`, so a grid sensor with a constant value is no longer treated as stale after 60 s.
- Energy sensors no longer count the same increment twice when the mode changes or a cable is plugged in.
- EV battery sensor values such as `80.0` are now accepted.
- If the charger current entity is `unavailable` or `unknown`, EVSCI no longer assumes 6 A and sends no commands until it is readable again.
- Bare `except:` clauses were narrowed to specific exceptions.
- README: start/stop buttons instead of the legacy charger switch, correct `number.target_soc` entity in the dashboard example.

## [0.2.1] - 2026-04-09
- Release that actually contains the changes listed under 0.2.0 (Target SoC `number` entity, state restore for mode and schedule, session tracking and start/stop button support). The 0.2.0 tag did not include them yet.

## [0.2.0] - 2026-04-06
- Configuration now asks for dedicated Charger Start and Charger Stop buttons (with legacy switch support still available) and the translations were updated so both languages describe the new controls.
- Target SoC is exposed as a new `number` entity that restores its last value, giving a quick UI control for the stop percentage while letting EVSCI remember it across restarts.
- Mode select plus schedule start/end times now restore their last saved state, keeping the previously chosen mode and schedule window active after HA reboots.
- Charging session tracking and actuation got overhauled: the coordinator now monitors actual power to recognize when a charge session is running, tracks plug/unplug events, enforces PV-only pause-and-resume hysteresis, and toggles the charger through the new button services (or the legacy switch) so that start/stop happens reliably.
