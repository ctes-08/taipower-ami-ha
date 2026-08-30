"""Constants for the Taipower AMI integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "taipower_ami"
NAME: Final = "Taipower AMI"

CONF_CREDENTIAL_FILE: Final = "credential_file"
CONF_UPDATE_INTERVAL: Final = "update_interval"

DEFAULT_CREDENTIAL_FILE: Final = ".taipower_ami/credentials.json"
DEFAULT_UPDATE_INTERVAL_MINUTES: Final = 120
MIN_UPDATE_INTERVAL_MINUTES: Final = 60
MAX_UPDATE_INTERVAL_MINUTES: Final = 1440

SERVICE_REFRESH_DATA: Final = "refresh_data"
ATTR_ENTRY_ID: Final = "entry_id"

STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.snapshot"
STORAGE_VERSION: Final = 1

PLATFORMS: Final = ("sensor", "button")
