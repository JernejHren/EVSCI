"""Izbirnik načina za EVSCI."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODES

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastavi select platformo."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EVSCIModeSelect(coordinator)], True)

class EVSCIModeSelect(CoordinatorEntity, SelectEntity):
    """Entiteta za izbiro načina polnjenja."""

    _attr_has_entity_name = True
    _attr_name = "Charging Mode"
    _attr_icon = "mdi:car-electric"
    _attr_options = MODES

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_mode_select"

    @property
    def current_option(self) -> str | None:
        """Vrne trenutno izbran način iz coordinatorja."""
        # Coordinator podatki se osvežijo v _async_update_data
        # Ampak ker način nastavljamo ročno, ga lahko beremo direktno iz spremenljivke
        return self.coordinator.selected_mode

    async def async_select_option(self, option: str) -> None:
        """Uporabnik spremeni način."""
        self.coordinator.set_mode(option)
        self.async_write_ha_state()
