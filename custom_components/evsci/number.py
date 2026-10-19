"""Number entitete za EVSCI."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import EVSCIConfigEntry
from .entity import EVSCIEntity


# Koordinator je en sam in pošilja ukaze polnilniku zaporedno; vzporednih posodobitev ne omejujemo
# z semaforjem, ker entitete same ne kličejo naprave.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EVSCIConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastavi number platformo."""
    coordinator = entry.runtime_data
    async_add_entities(
        [EVSCITargetSocNumber(coordinator), EVSCILowTariffBlockNumber(coordinator)]
    )


class EVSCITargetSocNumber(EVSCIEntity, NumberEntity, RestoreEntity):
    """Nastavitev ciljnega SoC (%), pri katerem se polnjenje ustavi."""

    _attr_translation_key = "target_soc"
    _attr_entity_category = EntityCategory.CONFIG
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


class EVSCILowTariffBlockNumber(EVSCIEntity, NumberEntity, RestoreEntity):
    """Najvišji dovoljeni blok za način Low Tariff: polni v tem bloku in v cenejših (višjih številkah)."""

    _attr_translation_key = "low_tariff_block"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_low_tariff_block"

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
        self.coordinator.user_low_tariff_block = max(1, min(5, restored))
        await self.coordinator.async_refresh()
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        return int(self.coordinator.user_low_tariff_block)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.user_low_tariff_block = max(1, min(5, int(value)))
        await self.coordinator.async_refresh()
        self.async_write_ha_state()
