"""Time entitete za nastavljanje urnika."""
import datetime
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Nastavi time entitete."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        EVSCIScheduleStart(coordinator),
        EVSCIScheduleEnd(coordinator),
    ], True)

class EVSCIScheduleStart(CoordinatorEntity, TimeEntity):
    """Ura za začetek polnjenja."""
    _attr_has_entity_name = True
    _attr_name = "Schedule Start"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_schedule_start"

    @property
    def native_value(self) -> datetime.time | None:
        """Preberi vrednost iz koordinatorja."""
        return self.coordinator.schedule_start

    async def async_set_value(self, value: datetime.time) -> None:
        """Shrani vrednost v koordinator."""
        self.coordinator.schedule_start = value
        # Sproži posodobitev, da se logika takoj preračuna
        await self.coordinator.async_refresh()

class EVSCIScheduleEnd(CoordinatorEntity, TimeEntity):
    """Ura za konec polnjenja."""
    _attr_has_entity_name = True
    _attr_name = "Schedule End"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_schedule_end"

    @property
    def native_value(self) -> datetime.time | None:
        return self.coordinator.schedule_end

    async def async_set_value(self, value: datetime.time) -> None:
        self.coordinator.schedule_end = value
        await self.coordinator.async_refresh()
