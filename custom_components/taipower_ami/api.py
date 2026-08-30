"""Pure, read-only client for the official Taipower AMI endpoints.

This module intentionally contains no Home Assistant imports. Network calls are
synchronous and MUST be executed through Home Assistant's executor by callers.
It never performs login automation and never logs credential-bearing values or
raw response bodies.
"""

from __future__ import annotations

import json
import socket
import ssl
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

BASE_URL = "https://service.taipower.com.tw"
API_ROOT = "/ebpps2/amichart/api"
SUCCESS_CODE = "AMI0000"
EMPTY_DATA_CODE = "AMIXXXX"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class AmiError(RuntimeError):
    """Base exception whose message never contains credentials or payloads."""


class AmiAuthenticationError(AmiError):
    """The imported browser session is missing, invalid, or expired."""


class AmiConnectionError(AmiError):
    """The official Taipower service could not be reached."""


class AmiProtocolError(AmiError):
    """The response did not match the expected AMI schema."""


@dataclass(frozen=True, slots=True)
class AmiCredentials:
    """Minimum credential material produced by the Windows companion."""

    session_value: str = field(repr=False)
    enkey: str = field(repr=False)
    imported_at: str
    captured_day: date | None = None

    @property
    def cookie_header(self) -> str:
        """Return the only cookie sent to Taipower."""

        return f"SESSION={self.session_value}"


@dataclass(frozen=True, slots=True)
class FifteenMinutePoint:
    """One 15-minute energy interval."""

    time_label: str
    energy_kwh: float | None
    missing: bool | None


@dataclass(frozen=True, slots=True)
class PeriodPoint:
    """One hourly, daily, or monthly tariff-period row."""

    unit: str
    off_peak_kwh: float | None
    semi_peak_kwh: float | None
    saturday_semi_peak_kwh: float | None
    peak_kwh: float | None
    total_kwh: float | None
    incomplete: bool | None


@dataclass(frozen=True, slots=True)
class ComparisonPoint:
    """One row comparing the same interval on two dates."""

    unit: str
    first_day_kwh: float | None
    second_day_kwh: float | None


@dataclass(frozen=True, slots=True)
class AmiSnapshot:
    """Sanitized result of one five-endpoint refresh."""

    fetched_at: datetime
    target_day: date
    fifteen_minutes: tuple[FifteenMinutePoint, ...]
    hourly: tuple[PeriodPoint, ...]
    daily: tuple[PeriodPoint, ...]
    monthly: tuple[PeriodPoint, ...]
    comparison: tuple[ComparisonPoint, ...]


def validate_credentials(credentials: AmiCredentials) -> AmiCredentials:
    """Validate imported values without returning them in an error."""

    _validate_opaque_value("SESSION", credentials.session_value)
    _validate_opaque_value("enkey", credentials.enkey)
    if not isinstance(credentials.imported_at, str) or not credentials.imported_at:
        raise AmiAuthenticationError("The credential import timestamp is missing")
    return credentials


def parse_fifteen_payload(payload: Mapping[str, Any]) -> list[FifteenMinutePoint]:
    """Parse the ``fifteenlist`` response without treating missing zeroes as data."""

    _validate_success(payload, "listAMIBase15MinData")
    rows = _require_rows(payload, "listAMIBase15MinData")
    points: list[FifteenMinutePoint] = []
    for row in rows:
        missing = _flag_or_none(row.get("isMssingData"))
        points.append(
            FifteenMinutePoint(
                time_label=_required_text(row, "time"),
                energy_kwh=(
                    _float_or_none(row.get("power")) if missing is False else None
                ),
                missing=missing,
            )
        )
    return points


def parse_period_payload(payload: Mapping[str, Any]) -> list[PeriodPoint]:
    """Parse hourly, daily, or monthly tariff columns without relabelling them."""

    _validate_success(payload, "listAMIBase4PeriodData")
    rows = _require_rows(payload, "listAMIBase4PeriodData")
    return [
        PeriodPoint(
            unit=_required_text(row, "chartUnit"),
            off_peak_kwh=_float_or_none(row.get("chartCol1")),
            semi_peak_kwh=_float_or_none(row.get("chartCol2")),
            saturday_semi_peak_kwh=_float_or_none(row.get("chartCol3")),
            peak_kwh=_float_or_none(row.get("chartCol4")),
            total_kwh=_float_or_none(row.get("chartCol5")),
            incomplete=_flag_or_none(row.get("isMssingData")),
        )
        for row in rows
    ]


def parse_comparison_payload(payload: Mapping[str, Any]) -> list[ComparisonPoint]:
    """Parse ``dayanddayalist`` columns as two dates, not tariff periods."""

    _validate_success(payload, "listAMIBase4PeriodData")
    rows = _require_rows(payload, "listAMIBase4PeriodData")
    return [
        ComparisonPoint(
            unit=_required_text(row, "chartUnit"),
            first_day_kwh=_float_or_none(row.get("chartCol1")),
            second_day_kwh=_float_or_none(row.get("chartCol2")),
        )
        for row in rows
    ]


class TaipowerWebClient:
    """Synchronous GET-only client using browser-created credentials."""

    def __init__(self, credentials: AmiCredentials, timeout: float = 20.0) -> None:
        self._credentials = validate_credentials(credentials)
        self._timeout = timeout
        self._opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(context=_create_https_context()),
            _NoRedirectHandler(),
        )

    def fetch_fifteen_minutes(self, target_day: date) -> list[FifteenMinutePoint]:
        """Fetch the official 15-minute data for one date."""

        return parse_fifteen_payload(
            self._get("fifteenlist", {"day": target_day.isoformat()})
        )

    def fetch_hourly(self, target_day: date) -> list[PeriodPoint]:
        """Fetch the official hourly tariff-period data for one date."""

        return parse_period_payload(
            self._get("daylist", {"day": target_day.isoformat()})
        )

    def fetch_daily(self, year: int, month: int) -> list[PeriodPoint]:
        """Fetch official daily rows for one Gregorian calendar month."""

        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        return parse_period_payload(
            self._get("monthlist", {"yyymm": f"{_roc_year(year):03d}-{month:02d}"})
        )

    def fetch_monthly(self, year: int) -> list[PeriodPoint]:
        """Fetch official monthly rows for one Gregorian calendar year."""

        return parse_period_payload(
            self._get("yearlist", {"year": f"{_roc_year(year):03d}"})
        )

    def fetch_comparison(
        self, first_day: date, second_day: date
    ) -> list[ComparisonPoint]:
        """Fetch official same-interval comparison rows for two dates."""

        return parse_comparison_payload(
            self._get(
                "dayanddayalist",
                {"day1": first_day.isoformat(), "day2": second_day.isoformat()},
            )
        )

    def fetch_snapshot(self, target_day: date) -> AmiSnapshot:
        """Fetch all five read-only endpoints used by the alpha integration."""

        from datetime import timedelta

        return AmiSnapshot(
            fetched_at=datetime.now(UTC),
            target_day=target_day,
            fifteen_minutes=tuple(self.fetch_fifteen_minutes(target_day)),
            hourly=tuple(self.fetch_hourly(target_day)),
            daily=tuple(self.fetch_daily(target_day.year, target_day.month)),
            monthly=tuple(self.fetch_monthly(target_day.year)),
            comparison=tuple(
                self.fetch_comparison(target_day - timedelta(days=1), target_day)
            ),
        )

    def _get(self, endpoint: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        query = urlencode({"enkey": self._credentials.enkey, **params})
        url = f"{BASE_URL}{API_ROOT}/{endpoint}?{query}"
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Cookie": self._credentials.cookie_header,
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise AmiConnectionError(
                        f"Taipower returned HTTP {response.status}"
                    )
                final_url = urlparse(response.geturl())
                if (
                    final_url.scheme != "https"
                    or final_url.hostname != "service.taipower.com.tw"
                    or final_url.path != f"{API_ROOT}/{endpoint}"
                ):
                    raise AmiProtocolError("Taipower response changed destination")
                if response.headers.get_content_type() != "application/json":
                    raise AmiConnectionError(
                        "Taipower temporarily returned a non-JSON response"
                    )
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308, 401, 403}:
                raise AmiAuthenticationError(
                    "The Taipower SESSION is invalid or expired"
                ) from None
            if exc.code == 429:
                raise AmiConnectionError("Taipower rate limited the request") from None
            raise AmiConnectionError(f"Taipower returned HTTP {exc.code}") from None
        except TimeoutError:
            raise AmiConnectionError("Taipower request timed out") from None
        except URLError as exc:
            raise AmiConnectionError(_connection_error_message(exc)) from None

        if len(raw) > MAX_RESPONSE_BYTES:
            raise AmiProtocolError("Taipower response exceeded the safety limit")
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AmiProtocolError("Taipower did not return valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise AmiProtocolError("Taipower JSON root is not an object")
        return payload


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, url):
        """Reject redirects so login pages cannot be mistaken for API data."""

        return None


def _create_https_context() -> ssl.SSLContext:
    """Create a verified context compatible with Taipower's legacy TWCA chain.

    Python 3.14 enables OpenSSL strict RFC 5280 validation by default.  The
    certificate chain currently served by Taipower contains an older
    intermediate without a Subject Key Identifier, so strict mode rejects it.
    Clear only that strict-mode flag while retaining CA trust, hostname,
    validity-period, and signature verification.
    """

    context = ssl.create_default_context()
    strict_flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict_flag:
        context.verify_flags &= ~strict_flag
    return context


def _connection_error_message(error: URLError) -> str:
    """Classify a connection failure without exposing its raw details."""

    reason = error.reason
    if isinstance(reason, ssl.SSLError):
        return "Taipower TLS verification failed"
    if isinstance(reason, socket.gaierror):
        return "Taipower DNS lookup failed"
    if isinstance(reason, TimeoutError):
        return "Taipower request timed out"
    return "Taipower connection failed"


def _validate_opaque_value(name: str, value: str) -> None:
    if not isinstance(value, str) or not 8 <= len(value) <= 512:
        raise AmiProtocolError(f"{name} has an unexpected length")
    if any(ord(character) < 0x20 or character.isspace() for character in value):
        raise AmiProtocolError(f"{name} contains invalid characters")


def _validate_success(payload: Mapping[str, Any], rows_key: str) -> None:
    code = payload.get("msgCode")
    if code == EMPTY_DATA_CODE and payload.get(rows_key) == []:
        # The AMI frontend uses this narrow shape for a valid requested period
        # that predates the meter's retained history.  It is successful empty
        # data, not a zero reading and not an authentication failure.
        return
    if code != SUCCESS_CODE:
        raise AmiProtocolError(f"Taipower returned API code {code!r}")


def _require_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise AmiProtocolError(f"Taipower field {key} is not a row list")
    return value


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value or len(value) > 64:
        raise AmiProtocolError(f"Taipower row field {key} is not text")
    return value


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AmiProtocolError("A numeric AMI field was boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AmiProtocolError("A numeric AMI field was invalid") from exc
    if number < 0 or number in {float("inf"), float("-inf")} or number != number:
        raise AmiProtocolError("A numeric AMI field was outside the valid range")
    return number


def _flag_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if value in {0, "0"}:
        return False
    if value in {1, "1"}:
        return True
    raise AmiProtocolError("An AMI missing-data flag was invalid")


def _roc_year(year: int) -> int:
    if year < 1912:
        raise ValueError("year must be Gregorian and at least 1912")
    return year - 1911
