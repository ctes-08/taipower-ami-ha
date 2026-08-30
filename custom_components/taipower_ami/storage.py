"""Credential-file and sanitized snapshot storage helpers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import (
    AmiAuthenticationError,
    AmiCredentials,
    AmiProtocolError,
    AmiSnapshot,
    validate_credentials,
)
from .const import STORAGE_KEY_PREFIX, STORAGE_VERSION

MAX_CREDENTIAL_BYTES = 64 * 1024


def resolve_credential_path(config_root: str, relative_path: str) -> Path:
    """Resolve a credential path and require it to stay inside HA config.

    This function performs filesystem I/O and MUST run in an executor.
    """

    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("credential path is empty")
    if "\x00" in relative_path:
        raise ValueError("credential path contains a NUL byte")
    candidate_input = Path(relative_path)
    if candidate_input.is_absolute():
        raise ValueError("credential path must be relative to Home Assistant config")

    try:
        root = Path(config_root).resolve(strict=True)
        unresolved = root
        for part in candidate_input.parts:
            unresolved /= part
            if unresolved.is_symlink():
                raise ValueError("credential path must not traverse a symbolic link")
        candidate = unresolved.resolve(strict=True)
    except OSError as exc:
        raise ValueError("credential path cannot be read") from exc
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("credential path leaves Home Assistant config") from exc
    if not candidate.is_file():
        raise ValueError("credential path is not a regular file")
    return candidate


def load_credentials_file(config_root: str, relative_path: str) -> AmiCredentials:
    """Load the minimal V1 handoff document without exposing its secrets.

    This function performs filesystem I/O and MUST run in an executor.
    """

    path = resolve_credential_path(config_root, relative_path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError("credential file cannot be read") from exc
    if not 0 < size <= MAX_CREDENTIAL_BYTES:
        raise ValueError("credential file has an unexpected size")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("credential file is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("credential file uses an unsupported format")

    captured_day_raw = payload.get("captured_day")
    try:
        captured_day = (
            date.fromisoformat(captured_day_raw)
            if isinstance(captured_day_raw, str)
            else None
        )
    except ValueError as exc:
        raise ValueError("credential captured_day is invalid") from exc

    try:
        credentials = AmiCredentials(
            session_value=payload.get("session"),
            enkey=payload.get("enkey"),
            imported_at=payload.get("imported_at"),
            captured_day=captured_day,
        )
        return validate_credentials(credentials)
    except (AmiAuthenticationError, AmiProtocolError) as exc:
        raise ValueError("credential file contains invalid values") from exc


class SanitizedSnapshotStore:
    """Persist only non-secret summary data for startup diagnostics."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry_id}",
            private=True,
        )

    async def async_load(self) -> dict[str, Any] | None:
        """Load the last sanitized summary."""

        return await self._store.async_load()

    async def async_save(self, snapshot: AmiSnapshot) -> None:
        """Save counts and derived totals, never rows or credentials."""

        await self._store.async_save(snapshot_summary(snapshot))


def snapshot_summary(snapshot: AmiSnapshot) -> dict[str, Any]:
    """Return a JSON-safe, credential-free summary."""

    return {
        "fetched_at": snapshot.fetched_at.isoformat(),
        "target_day": snapshot.target_day.isoformat(),
        "row_counts": {
            "fifteen_minutes": len(snapshot.fifteen_minutes),
            "hourly": len(snapshot.hourly),
            "daily": len(snapshot.daily),
            "monthly": len(snapshot.monthly),
            "comparison": len(snapshot.comparison),
        },
        "values": derived_values(snapshot),
    }


def derived_values(snapshot: AmiSnapshot) -> dict[str, float | None]:
    """Calculate compact public sensor values from normalized rows."""

    latest = next(
        (
            point.energy_kwh
            for point in reversed(snapshot.fifteen_minutes)
            if point.energy_kwh is not None
        ),
        None,
    )
    return {
        "latest_15m": latest,
        "today": _sum_period_totals(snapshot.hourly),
        "this_month": _sum_period_totals(snapshot.daily),
        "this_year": _sum_period_totals(snapshot.monthly),
        "comparison_delta": _comparison_delta(snapshot),
    }


def _sum_period_totals(rows: tuple[Any, ...]) -> float | None:
    values = [row.total_kwh for row in rows if row.total_kwh is not None]
    return round(sum(values), 6) if values else None


def _comparison_delta(snapshot: AmiSnapshot) -> float | None:
    first = [
        row.first_day_kwh
        for row in snapshot.comparison
        if row.first_day_kwh is not None
    ]
    second = [
        row.second_day_kwh
        for row in snapshot.comparison
        if row.second_day_kwh is not None
    ]
    if not first or not second:
        return None
    return round(sum(second) - sum(first), 6)
