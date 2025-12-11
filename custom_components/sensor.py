"""Senzorji za EVSCI."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    RestoreSensor, # NOVO: Za lifetime senzorje
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfPower, UnitOfElectricCurrent, UnitOfEnergy

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Nastavi senzorje."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        EVSCITargetCurrent(coordinator),
        EVSCIGridMonitor(coordinator),
        EVSCITariffMonitor(coordinator),
        
        # NOVO: Energetski senzorji
        EVSCISessionEnergy(coordinator, "session_total", "Session Energy Total"),
        EVSCISessionEnergy(coordinator, "session_solar", "Session Energy Solar"),
        EVSCISessionEnergy(coordinator, "session_grid", "Session Energy Grid"),
        
        EVSCILifetimeEnergy(coordinator, "lifetime_total", "Lifetime Energy Total"),
        EVSCILifetimeEnergy(coordinator, "lifetime_solar", "Lifetime Energy Solar"),
        EVSCILifetimeEnergy(coordinator, "lifetime_grid", "Lifetime Energy Grid"),
    ]
    
    if coordinator.data and coordinator.data.get("solar_power") is not None:
         sensors.append(EVSCISolarMonitor(coordinator))

    async_add_entities(sensors, True)


class EVSCIBaseSensor(CoordinatorEntity, SensorEntity):
    """Osnovni razred."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._entry_id = coordinator.entry.entry_id

class EVSCITargetCurrent(EVSCIBaseSensor):
    _attr_name = "Target Current"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_icon = "mdi:current-ac"
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_target_curr"
    @property
    def native_value(self):
        return self.coordinator.data.get("target_current", 0)

class EVSCIGridMonitor(EVSCIBaseSensor):
    _attr_name = "Monitored Grid Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_mon_grid"
    @property
    def native_value(self):
        return self.coordinator.data.get("grid_power", 0)

class EVSCISolarMonitor(EVSCIBaseSensor):
    _attr_name = "Monitored Solar Power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_mon_solar"
    @property
    def native_value(self):
        return self.coordinator.data.get("solar_power", 0)

class EVSCITariffMonitor(EVSCIBaseSensor):
    _attr_name = "Monitored Tariff Block"
    _attr_icon = "mdi:cash-clock"
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry_id}_mon_tariff"
    @property
    def native_value(self):
        return self.coordinator.data.get("tariff", 1)

# --- NOVI RAZREDI ZA ENERGIJO ---

class EVSCISessionEnergy(EVSCIBaseSensor):
    """Senzor za energijo seje (resetira se ob priklopu)."""
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    
    def __init__(self, coordinator, key_type, name):
        super().__init__(coordinator)
        self._key_type = key_type # 'session_total', 'session_solar', 'session_grid'
        self._attr_name = name
        self._attr_unique_id = f"{self._entry_id}_{key_type}"
        self._state = 0.0

    @property
    def native_value(self):
        return self._state

    @property
    def icon(self):
        if "solar" in self._key_type: return "mdi:solar-power"
        if "grid" in self._key_type: return "mdi:transmission-tower"
        return "mdi:ev-station"

    def _handle_coordinator_update(self) -> None:
        """Kliče se vsakih 5 sekund, ko coordinator objavi nove podatke."""
        data = self.coordinator.data
        
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
    
    def __init__(self, coordinator, key_type, name):
        super().__init__(coordinator)
        self._key_type = key_type
        self._attr_name = name
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
    def native_value(self):
        return self._state
        
    @property
    def icon(self):
        if "solar" in self._key_type: return "mdi:solar-power"
        if "grid" in self._key_type: return "mdi:transmission-tower"
        return "mdi:counter"

    def _handle_coordinator_update(self) -> None:
        """Prištej prirastek."""
        data = self.coordinator.data
        
        inc_grid = data.get("energy_inc_grid", 0.0)
        inc_solar = data.get("energy_inc_solar", 0.0)
        
        if "solar" in self._key_type:
            self._state += inc_solar
        elif "grid" in self._key_type:
            self._state += inc_grid
        else: # Total
            self._state += (inc_grid + inc_solar)
            
        self.async_write_ha_state()
