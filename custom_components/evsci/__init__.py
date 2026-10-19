"""EVSCI Integracija - Inicializacija."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import EVSCIConfigEntry, EVSCICoordinator

PLATFORMS = ["select", "sensor", "time", "number"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: EVSCIConfigEntry) -> bool:
    """Nastavi integracijo."""
    coordinator = EVSCICoordinator(hass, entry)

    # Ob zagonu HA se vhodne entitete lahko naložijo kasneje kot ta integracija.
    # Če jih ni, poskusimo znova, namesto da bi delovali z nepopolnimi podatki.
    missing = coordinator.missing_entities()
    if missing:
        raise ConfigEntryNotReady(
            f"Entities not available yet: {', '.join(missing)}"
        )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EVSCIConfigEntry) -> bool:
    """Odstrani integracijo."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.clear_issues()
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: EVSCIConfigEntry) -> None:
    """Sprememba nastavitev."""
    await hass.config_entries.async_reload(entry.entry_id)
