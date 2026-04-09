"""Number entitete za EVSCI."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastavi number platformo."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EVSCITargetSocNumber(coordinator)], True)


class EVSCITargetSocNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    """Nastavitev ciljnega SoC (%), pri katerem se polnjenje ustavi."""

    _attr_has_entity_name = True
    _attr_name = "Target SoC"
    _attr_icon = "mdi:battery-heart-variant"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_target_soc"

    async def async_added_to_hass(self) -> None:
        """Ob zagonu obnovi zadnjo vrednost."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state or last_state.state in ("unknown", "unavailable"):
            return

        try:
            restored = int(float(last_state.state))
        except (ValueError, TypeError):
            return

        self.coordinator.user_target_soc = max(0, min(100, restored))
        await self.coordinator.async_refresh()
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Trenutni ciljni SoC."""
        return int(self.coordinator.user_target_soc)

    async def async_set_native_value(self, value: float) -> None:
        """Uporabnik spremeni ciljni SoC."""
        self.coordinator.user_target_soc = int(value)
        await self.coordinator.async_refresh()
        self.async_write_ha_state()
