"""Skupni osnovni razred entitet EVSCI."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EVSCICoordinator


class EVSCIEntity(CoordinatorEntity[EVSCICoordinator]):
    """Osnova za vse entitete: poskrbi za napravo in ime entitete."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EVSCICoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.entry.entry_id
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="EV Smart Charging",
            manufacturer="EVSCI",
            model="Smart charging controller",
            entry_type=DeviceEntryType.SERVICE,
        )
