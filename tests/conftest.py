"""Shared fixtures for tests that use a real Home Assistant runtime."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations) -> None:
    """Allow Home Assistant to load this repository's custom integration."""
