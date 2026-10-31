"""Senzorji za EVSCI."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    RestoreSensor, # NOVO: Za lifetime senzorje
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfPower, UnitOfElectricCurrent, UnitOfEnergy

from .coordinator import EVSCIConfigEntry, EVSCICoordinator
from .entity import EVSCIEntity

# Koordinator je en sam in pošilja ukaze polnilniku zaporedno; vzporednih posodobitev ne omejujemo
# z semaforjem, ker entitete same ne kličejo naprave.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: EVSCIConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Nastavi senzorje."""
    coordinator = entry.runtime_data
    
    sensors = [
        EVSCITargetCurrent(coordinator),
        EVSCIGridMonitor(coordinator),
        EVSCITariffMonitor(coordinator),
        
        # NOVO: Energetski senzorji
        EVSCISessionEnergy(coordinator, "session_total"),
        EVSCISessionEnergy(coordinator, "session_solar"),
        EVSCISessionEnergy(coordinator, "session_grid"),
        
        EVSCILifetimeEnergy(coordinator, "lifetime_total"),
        EVSCILifetimeEnergy(coordinator, "lifetime_solar"),
        EVSCILifetimeEnergy(coordinator, "lifetime_grid"),
    ]

    async_add_entities(sensors)


class EVSCIBaseSensor(EVSCIEntity, SensorEntity):
    """Osnovni razred."""
    def __init__(self, coordinator: EVSCICoordinator) -> None:
        super().__init__(coordinator)
        self._last_update_id: int | None = None

    # Ključ v podatkih koordinatorja, ki pove, ali je vhodni signal te entitete na voljo.
    # None = entiteta je vedno razpoložljiva (števci hranijo zadnjo vrednost).
    _availability_key: str | None = None

    @property
    def available(self) -> bool:
        """Entiteta je nedosegljiva, ko manjka vhodni signal, ki ga prikazuje."""
        if not super().available:
            return False
        if self._availability_key is None:
            return True
        return bool((self.coordinator.data or {}).get(self._availability_key, True))

    def _is_new_update(self, data: dict[str, Any]) -> bool:
        """Ali gre za nov izračun koordinatorja.

        Koordinator ob spremembi načina ali ob priklopu ponovno objavi stare
        podatke. Prirastke energije smemo prišteti samo enkrat na izračun.
        """
        update_id = data.get("update_id")
        if update_id is not None and update_id == self._last_update_id:
            return False
        self._last_update_id = update_id
        return True

class EVSCITargetCurrent(EVSCIBaseSensor):
    _attr_translation_key = "target_current"
    _availability_key = "inputs_ok"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    def __init__(self, coordinator: EVSCICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_target_curr"
    @property
    def native_value(self) -> float:
        value: float = self.coordinator.data.get("target_current", 0)
        return value

class EVSCIGridMonitor(EVSCIBaseSensor):
    _attr_translation_key = "monitored_grid_power"
    _availability_key = "grid_ok"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator: EVSCICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_mon_grid"
    @property
    def native_value(self) -> float:
        value: float = self.coordinator.data.get("grid_power", 0)
        return value

class EVSCITariffMonitor(EVSCIBaseSensor):
    _attr_translation_key = "monitored_tariff_block"
    _availability_key = "tariff_ok"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self, coordinator: EVSCICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_mon_tariff"
    @property
    def native_value(self) -> float:
        value: int = self.coordinator.data.get("tariff", 1)
        return value

# --- NOVI RAZREDI ZA ENERGIJO ---

class EVSCISessionEnergy(EVSCIBaseSensor):
    """Senzor za energijo seje (resetira se ob priklopu)."""
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    
    def __init__(self, coordinator: EVSCICoordinator, key_type: str) -> None:
        super().__init__(coordinator)
        self._key_type = key_type # 'session_total', 'session_solar', 'session_grid'
        self._attr_translation_key = key_type
        self._attr_unique_id = f"{self._entry_id}_{key_type}"
        self._state = 0.0

    @property
    def native_value(self) -> float:
        return self._state

    def _handle_coordinator_update(self) -> None:
        """Kliče se vsakih 5 sekund, ko coordinator objavi nove podatke."""
        data = self.coordinator.data

        if not self._is_new_update(data):
            self.async_write_ha_state()
            return

        # Preveri za reset signal
        if data.get("reset_session"):
            self._state = 0.0
        
        # Preberi prirastek (increment)
        inc_grid = data.get("energy_inc_grid", 0.0)
        inc_solar = data.get("energy_inc_solar", 0.0)
        
        # Prištej glede na tip senzorja
        if "solar" in self._key_type:
            self._state += inc_solar
        elif "grid" in self._key_type:
            self._state += inc_grid
        else: # Total
            self._state += (inc_grid + inc_solar)
            
        self.async_write_ha_state()


class EVSCILifetimeEnergy(EVSCIBaseSensor, RestoreSensor):
    """Trajni števec energije (se ne resetira, ohrani stanje ob restartu)."""
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    def __init__(self, coordinator: EVSCICoordinator, key_type: str) -> None:
        super().__init__(coordinator)
        self._key_type = key_type
        self._attr_translation_key = key_type
        self._attr_unique_id = f"{self._entry_id}_{key_type}"
        self._state = 0.0

    async def async_added_to_hass(self) -> None:
        """Ob zagonu obnovi zadnje stanje."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            try:
                self._state = float(last_state.state)
            except (ValueError, TypeError):
                self._state = 0.0

    @property
    def native_value(self) -> float:
        return self._state
        
    def _handle_coordinator_update(self) -> None:
        """Prištej prirastek."""
        data = self.coordinator.data

        if not self._is_new_update(data):
            self.async_write_ha_state()
            return

        inc_grid = data.get("energy_inc_grid", 0.0)
        inc_solar = data.get("energy_inc_solar", 0.0)
        
        if "solar" in self._key_type:
            self._state += inc_solar
        elif "grid" in self._key_type:
            self._state += inc_grid
        else: # Total
            self._state += (inc_grid + inc_solar)
            
        self.async_write_ha_state()
