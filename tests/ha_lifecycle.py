"""Isolated lifecycle tests using the real Home Assistant test runtime.

The pytest Home Assistant plugin blocks non-local sockets before every test.
All Taipower client work is additionally replaced with deterministic snapshots,
so this module never reads a real handoff or contacts the official service.
"""

from __future__ import annotations

import json
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.taipower_ami.api import (
    AmiSnapshot,
    ComparisonPoint,
    FifteenMinutePoint,
    PeriodPoint,
)
from custom_components.taipower_ami.const import (
    CONF_CREDENTIAL_FILE,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_REFRESH_DATA,
)
from custom_components.taipower_ami.diagnostics import (
    async_get_config_entry_diagnostics,
)

FAKE_CREDENTIAL_FILE = ".taipower_ami/lifecycle.json"
FAKE_SESSION = "opaque_session_lifecycle_12345"
FAKE_ENKEY = "opaque_enkey_lifecycle_12345"


def _snapshot() -> AmiSnapshot:
    """Return a small, secret-free snapshot for lifecycle assertions."""

    return AmiSnapshot(
        fetched_at=datetime(2030, 1, 2, 3, 4, tzinfo=UTC),
        target_day=date(2030, 1, 2),
        fifteen_minutes=(FifteenMinutePoint("00:15", 0.25, False),),
        hourly=(PeriodPoint("0", None, None, None, None, 1.25, False),),
        daily=(PeriodPoint("1", None, None, None, None, 12.5, False),),
        monthly=(PeriodPoint("1", None, None, None, None, 125.0, False),),
        comparison=(ComparisonPoint("0", 0.5, 0.75),),
    )


def _write_fake_credentials(hass: HomeAssistant) -> None:
    """Create a valid fake handoff inside the disposable HA config dir."""

    target = Path(hass.config.path(FAKE_CREDENTIAL_FILE))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "session": FAKE_SESSION,
                "enkey": FAKE_ENKEY,
                "imported_at": "2030-01-02T03:00:00+00:00",
                "captured_day": "2030-01-02",
            }
        ),
        encoding="utf-8",
    )


def _new_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Taipower AMI test",
        unique_id=DOMAIN,
        data={
            CONF_CREDENTIAL_FILE: FAKE_CREDENTIAL_FILE,
            CONF_UPDATE_INTERVAL: 120,
        },
    )


def test_harness_blocks_outbound_network() -> None:
    """Fail closed if the Home Assistant pytest socket guard is absent."""

    assert socket.socket.__name__ == "GuardedSocket"
    assert socket.socket.__module__ == "pytest_socket"


async def test_setup_refresh_reauth_unload_remove_readd_and_diagnostics(
    hass: HomeAssistant,
) -> None:
    """Exercise the public integration lifecycle without external I/O."""

    _write_fake_credentials(hass)
    entry = _new_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.taipower_ami.coordinator._fetch_snapshot_sync",
        return_value=_snapshot(),
    ) as fetch_snapshot:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert fetch_snapshot.call_count == 1
        assert hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA)
        registry = er.async_get(hass)
        assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 7

        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            {"entry_id": entry.entry_id},
            blocking=True,
        )
        assert fetch_snapshot.call_count == 2

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        serialized_diagnostics = json.dumps(
            diagnostics, sort_keys=True, default=str
        )
        assert diagnostics["contains_credentials"] is False
        assert diagnostics["last_update_success"] is True
        assert diagnostics["snapshot"]["values"]["today"] == 1.25
        assert FAKE_CREDENTIAL_FILE not in serialized_diagnostics
        assert FAKE_SESSION not in serialized_diagnostics
        assert FAKE_ENKEY not in serialized_diagnostics

        reauth = await entry.start_reauth_flow(hass)
        assert reauth["type"] is FlowResultType.FORM
        assert reauth["step_id"] == "reauth_confirm"
        reauth_done = await hass.config_entries.flow.async_configure(
            reauth["flow_id"], {}
        )
        await hass.async_block_till_done()
        assert reauth_done["type"] is FlowResultType.ABORT
        assert reauth_done["reason"] == "reauth_successful"
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert DOMAIN not in hass.data

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        removal = await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert removal == {"require_restart": False}
        assert hass.config_entries.async_get_entry(entry.entry_id) is None
        assert not er.async_entries_for_config_entry(registry, entry.entry_id)

        replacement = _new_entry()
        replacement.add_to_hass(hass)
        assert await hass.config_entries.async_setup(replacement.entry_id)
        await hass.async_block_till_done()
        assert replacement.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(replacement.entry_id)
        await hass.async_block_till_done()
