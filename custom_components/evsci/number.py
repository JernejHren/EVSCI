"""Number entitete za EVSCI."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastavi number entitete."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EVSCITargetSOC(coordinator)], True)


class EVSCITargetSOC(CoordinatorEntity, NumberEntity):
    """Nastavljiva ciljna vrednost napolnjenosti baterije (SOC)."""

    _attr_has_entity_name = True
    _attr_name = "Target SOC"
    _attr_icon = "mdi:battery-charging-high"
    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_target_soc"

    @property
    def native_value(self) -> float:
        """Preberi trenutno nastavljeno ciljno vrednost SOC."""
        return float(self.coordinator.user_target_soc)

    async def async_set_native_value(self, value: float) -> None:
        """Nastavi novo ciljno vrednost SOC."""
        self.coordinator.user_target_soc = int(value)
        await self.coordinator.async_refresh()
