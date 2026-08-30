from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "taipower_ami"
TEST_PACKAGE = "_taipower_ami_storage_test"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_storage_module():
    """Load storage helpers without importing a full Home Assistant runtime."""

    package = types.ModuleType(TEST_PACKAGE)
    package.__path__ = [str(INTEGRATION)]
    sys.modules[TEST_PACKAGE] = package

    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    helpers_storage = types.ModuleType("homeassistant.helpers.storage")

    class HomeAssistant:
        pass

    class Store:
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, *_args, **_kwargs):
            pass

    core.HomeAssistant = HomeAssistant
    helpers_storage.Store = Store
    homeassistant.core = core
    homeassistant.helpers = helpers
    helpers.storage = helpers_storage
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.storage": helpers_storage,
        }
    )

    _load_module(f"{TEST_PACKAGE}.api", INTEGRATION / "api.py")
    const = _load_module(f"{TEST_PACKAGE}.const", INTEGRATION / "const.py")
    sys.modules[f"{TEST_PACKAGE}.const"] = const
    return _load_module(f"{TEST_PACKAGE}.storage", INTEGRATION / "storage.py")


storage = _load_storage_module()


class CredentialFileTests(unittest.TestCase):
    def _write_credentials(self, root: Path) -> Path:
        target = root / ".taipower_ami" / "credentials.json"
        target.parent.mkdir()
        target.write_text(
            json.dumps(
                {
                    "version": 1,
                    "session": "opaque_session_12345",
                    "enkey": "opaque_enkey_12345",
                    "imported_at": "2026-08-28T00:00:00+08:00",
                    "captured_day": "2026-08-28",
                }
            ),
            encoding="utf-8",
        )
        return target

    def test_loads_valid_relative_utf8_file_without_secret_repr(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_credentials(root)

            credentials = storage.load_credentials_file(
                str(root), ".taipower_ami/credentials.json"
            )

            self.assertEqual(credentials.captured_day.isoformat(), "2026-08-28")
            self.assertNotIn("opaque_session_12345", repr(credentials))
            self.assertNotIn("opaque_enkey_12345", repr(credentials))

    def test_rejects_absolute_and_parent_escape_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self._write_credentials(root)

            with self.assertRaisesRegex(ValueError, "relative"):
                storage.resolve_credential_path(str(root), str(target.resolve()))
            with self.assertRaises(ValueError):
                storage.resolve_credential_path(
                    str(root), "../outside/credentials.json"
                )

    def test_rejects_oversized_and_malformed_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self._write_credentials(root)
            target.write_bytes(b"x" * (storage.MAX_CREDENTIAL_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "unexpected size"):
                storage.load_credentials_file(
                    str(root), ".taipower_ami/credentials.json"
                )

            target.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "UTF-8 JSON"):
                storage.load_credentials_file(
                    str(root), ".taipower_ami/credentials.json"
                )


if __name__ == "__main__":
    unittest.main()
