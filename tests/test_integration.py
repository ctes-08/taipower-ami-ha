from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "taipower_ami"
TEST_PACKAGE = "_taipower_ami_integration_test"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_integration_module():
    package = types.ModuleType(TEST_PACKAGE)
    package.__path__ = [str(INTEGRATION)]
    sys.modules[TEST_PACKAGE] = package

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Optional = lambda key: key
    voluptuous.Schema = lambda schema: schema

    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    exceptions = types.ModuleType("homeassistant.exceptions")
    helpers = types.ModuleType("homeassistant.helpers")
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    helpers_typing = types.ModuleType("homeassistant.helpers.typing")

    class ConfigEntry:
        pass

    class HomeAssistant:
        pass

    class ServiceCall:
        pass

    class ServiceValidationError(Exception):
        pass

    class Platform:
        SENSOR = "sensor"
        BUTTON = "button"

    config_entries.ConfigEntry = ConfigEntry
    const.CONF_ENTRY_ID = "entry_id"
    const.Platform = Platform
    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall
    exceptions.ServiceValidationError = ServiceValidationError
    config_validation.string = str
    helpers.config_validation = config_validation
    helpers_typing.ConfigType = dict

    homeassistant.config_entries = config_entries
    homeassistant.const = const
    homeassistant.core = core
    homeassistant.exceptions = exceptions
    homeassistant.helpers = helpers
    sys.modules.update(
        {
            "voluptuous": voluptuous,
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": const,
            "homeassistant.core": core,
            "homeassistant.exceptions": exceptions,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.config_validation": config_validation,
            "homeassistant.helpers.typing": helpers_typing,
        }
    )

    coordinator = types.ModuleType(f"{TEST_PACKAGE}.coordinator")

    class TaipowerAmiCoordinator:
        pass

    coordinator.TaipowerAmiCoordinator = TaipowerAmiCoordinator
    sys.modules[f"{TEST_PACKAGE}.coordinator"] = coordinator
    _load_module(f"{TEST_PACKAGE}.const", INTEGRATION / "const.py")
    return _load_module(TEST_PACKAGE, INTEGRATION / "__init__.py")


integration = _load_integration_module()


class FakeServiceRegistry:
    def __init__(self):
        self.handlers = {}
        self.removed = []

    def has_service(self, domain, service):
        return (domain, service) in self.handlers

    def async_register(self, domain, service, handler, **_kwargs):
        self.handlers[domain, service] = handler

    def async_remove(self, domain, service):
        self.removed.append((domain, service))
        self.handlers.pop((domain, service), None)


class FakeConfigEntries:
    async def async_unload_platforms(self, _entry, _platforms):
        return True


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FakeServiceRegistry()
        self.config_entries = FakeConfigEntries()


class RefreshCoordinator:
    def __init__(self):
        self.refreshes = 0

    async def async_request_refresh(self):
        self.refreshes += 1


class IntegrationServiceTests(unittest.TestCase):
    def test_async_setup_registers_service_and_rejects_unknown_entry(self):
        hass = FakeHass()

        self.assertTrue(asyncio.run(integration.async_setup(hass, {})))
        handler = hass.services.handlers[
            integration.DOMAIN, integration.SERVICE_REFRESH_DATA
        ]

        call = types.SimpleNamespace(data={"entry_id": "missing-entry"})
        with self.assertRaisesRegex(
            integration.ServiceValidationError, "missing-entry"
        ):
            asyncio.run(handler(call))

    def test_service_refreshes_loaded_entry_and_survives_last_unload(self):
        hass = FakeHass()
        coordinator = RefreshCoordinator()
        hass.data[integration.DOMAIN] = {"entry-1": coordinator}
        entry = types.SimpleNamespace(entry_id="entry-1")

        asyncio.run(integration.async_setup(hass, {}))
        handler = hass.services.handlers[
            integration.DOMAIN, integration.SERVICE_REFRESH_DATA
        ]
        asyncio.run(handler(types.SimpleNamespace(data={"entry_id": "entry-1"})))

        self.assertEqual(coordinator.refreshes, 1)
        self.assertTrue(asyncio.run(integration.async_unload_entry(hass, entry)))
        self.assertNotIn(integration.DOMAIN, hass.data)
        self.assertEqual(hass.services.removed, [])
        self.assertIn(
            (integration.DOMAIN, integration.SERVICE_REFRESH_DATA),
            hass.services.handlers,
        )

    def test_service_without_entry_id_refreshes_all_loaded_entries(self):
        hass = FakeHass()
        first = RefreshCoordinator()
        second = RefreshCoordinator()
        hass.data[integration.DOMAIN] = {"first": first, "second": second}

        asyncio.run(integration.async_setup(hass, {}))
        handler = hass.services.handlers[
            integration.DOMAIN, integration.SERVICE_REFRESH_DATA
        ]
        asyncio.run(handler(types.SimpleNamespace(data={})))

        self.assertEqual((first.refreshes, second.refreshes), (1, 1))


if __name__ == "__main__":
    unittest.main()
