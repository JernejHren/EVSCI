"""Diagnostika za EVSCI (prenos iz nastavitev naprave)."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import EVSCIConfigEntry


def _entity_state(hass: HomeAssistant, entity_id: str | None) -> dict[str, Any] | None:
    """Stanje vhodne entitete ali None, če entitete ni nastavljene."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return {"entity_id": entity_id, "state": "missing"}
    last_seen = state.last_reported or state.last_updated
    return {
        "entity_id": entity_id,
        "state": state.state,
        "last_reported": last_seen.isoformat() if last_seen else None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EVSCIConfigEntry
) -> dict[str, Any]:
    """Vrne nastavitve, notranje stanje in stanje vhodnih entitet."""
    coordinator = entry.runtime_data
    inputs = {
        "grid": coordinator.grid_entity,
        "charger_current": coordinator.charger_current_entity,
        "charger_power": coordinator.charger_power_entity,
        "charger_status": coordinator.charger_status_entity,
        "tariff": coordinator.tariff_entity,
        "ev_soc": coordinator.ev_soc_entity,
        "start_button": coordinator.charger_start_button_entity,
        "stop_button": coordinator.charger_stop_button_entity,
        "switch": coordinator.charger_switch_entity,
    }
    for index, entity_id in enumerate(coordinator.phase_entities, start=1):
        inputs[f"phase_l{index}"] = entity_id

    return {
        "config_entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "settings": asdict(coordinator.settings),
        "runtime": {
            "mode": coordinator.selected_mode,
            "is_charging": coordinator.is_charging,
            "session_active": coordinator._session_active,
            "pv_only_paused": coordinator._pv_only_paused,
            "cable_connected": coordinator._cable_connected,
            "target_soc": coordinator.user_target_soc,
            "low_tariff_block": coordinator.user_low_tariff_block,
            "schedule_start": coordinator.schedule_start.isoformat(),
            "schedule_end": coordinator.schedule_end.isoformat(),
            "last_valid_tariff": coordinator._last_valid_tariff,
            "tariff_seen_valid": coordinator._tariff_seen_valid,
            "idle_statuses": list(coordinator.idle_statuses),
            "active_issues": sorted(coordinator._active_issues),
        },
        "last_result": dict(coordinator.data) if coordinator.data else None,
        "input_states": {name: _entity_state(hass, entity_id) for name, entity_id in inputs.items()},
    }
