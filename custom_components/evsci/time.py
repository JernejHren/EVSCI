"""Time entitete za nastavljanje urnika."""
import datetime
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
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

class EVSCIScheduleStart(CoordinatorEntity, TimeEntity, RestoreEntity):
    """Ura za začetek polnjenja."""
    _attr_has_entity_name = True
    _attr_name = "Schedule Start"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_schedule_start"

    async def async_added_to_hass(self) -> None:
        """Ob zagonu obnovi zadnjo nastavljeno uro začetka."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self.coordinator.schedule_start = datetime.time.fromisoformat(last_state.state)
                await self.coordinator.async_refresh()
                self.async_write_ha_state()
            except ValueError:
                pass

    @property
    def native_value(self) -> datetime.time | None:
        """Preberi vrednost iz koordinatorja."""
        return self.coordinator.schedule_start

    async def async_set_value(self, value: datetime.time) -> None:
        """Shrani vrednost v koordinator."""
        self.coordinator.schedule_start = value
        # Sproži posodobitev, da se logika takoj preračuna
        await self.coordinator.async_refresh()

class EVSCIScheduleEnd(CoordinatorEntity, TimeEntity, RestoreEntity):
    """Ura za konec polnjenja."""
    _attr_has_entity_name = True
    _attr_name = "Schedule End"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_schedule_end"

    async def async_added_to_hass(self) -> None:
        """Ob zagonu obnovi zadnjo nastavljeno uro konca."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self.coordinator.schedule_end = datetime.time.fromisoformat(last_state.state)
                await self.coordinator.async_refresh()
                self.async_write_ha_state()
            except ValueError:
                pass

    @property
    def native_value(self) -> datetime.time | None:
        return self.coordinator.schedule_end

    async def async_set_value(self, value: datetime.time) -> None:
        self.coordinator.schedule_end = value
        await self.coordinator.async_refresh()
