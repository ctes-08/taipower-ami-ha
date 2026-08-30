"""Data coordinator for Taipower AMI."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import update_coordinator
from homeassistant.util import dt as dt_util

from .api import (
    AmiAuthenticationError,
    AmiConnectionError,
    AmiProtocolError,
    AmiSnapshot,
    TaipowerWebClient,
)
from .const import (
    CONF_CREDENTIAL_FILE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_CREDENTIAL_FILE,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
)
from .storage import SanitizedSnapshotStore, load_credentials_file

_LOGGER = logging.getLogger(__name__)


class TaipowerAmiCoordinator(update_coordinator.DataUpdateCoordinator[AmiSnapshot]):
    """Fetch all supported endpoints without blocking Home Assistant's loop."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        interval = int(
            entry.options.get(
                CONF_UPDATE_INTERVAL,
                entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES),
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
        )
        self._credential_file = str(
            entry.options.get(
                CONF_CREDENTIAL_FILE,
                entry.data.get(CONF_CREDENTIAL_FILE, DEFAULT_CREDENTIAL_FILE),
            )
        )
        self.store = SanitizedSnapshotStore(hass, entry.entry_id)

    async def _async_update_data(self) -> AmiSnapshot:
        """Load credentials and perform all synchronous work in the executor."""

        try:
            snapshot = await self.hass.async_add_executor_job(
                _fetch_snapshot_sync,
                self.hass.config.config_dir,
                self._credential_file,
                dt_util.now().date(),
            )
        except (AmiAuthenticationError, ValueError) as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except (AmiConnectionError, AmiProtocolError) as exc:
            raise update_coordinator.UpdateFailed(str(exc)) from exc

        await self.store.async_save(snapshot)
        return snapshot


def _fetch_snapshot_sync(config_root: str, credential_file: str, target_day):
    """Read the handoff file and call Taipower; executor use is mandatory."""

    credentials = load_credentials_file(config_root, credential_file)
    return TaipowerWebClient(credentials).fetch_snapshot(target_day)
