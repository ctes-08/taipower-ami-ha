from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "taipower_ami"


class RepositoryContractTests(unittest.TestCase):
    def test_required_hacs_files_exist(self):
        required = {
            ROOT / "README.md",
            ROOT / "hacs.json",
            INTEGRATION / "manifest.json",
            INTEGRATION / "__init__.py",
            INTEGRATION / "config_flow.py",
            INTEGRATION / "coordinator.py",
            INTEGRATION / "api.py",
            INTEGRATION / "storage.py",
            INTEGRATION / "sensor.py",
            INTEGRATION / "button.py",
            INTEGRATION / "services.yaml",
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "zh-Hant.json",
            INTEGRATION / "diagnostics.py",
        }
        self.assertEqual(
            [], sorted(str(path) for path in required if not path.is_file())
        )

    def test_manifest_keeps_alpha_identity(self):
        manifest = json.loads(
            (INTEGRATION / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["domain"], "taipower_ami")
        self.assertEqual(manifest["iot_class"], "cloud_polling")
        self.assertTrue(manifest["config_flow"])
        self.assertIn("alpha", manifest["version"])

    def test_public_source_contains_no_private_environment_values(self):
        forbidden_patterns = {
            "private or loopback IPv4 address": re.compile(
                r"(?<!\d)(?:10|127)(?:\.\d{1,3}){3}"
                r"|(?<!\d)192\.168(?:\.\d{1,3}){2}"
                r"|(?<!\d)172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
            ),
            "absolute Windows user-profile path": re.compile(
                r"\b[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE
            ),
            "private development tree": re.compile(
                r"\b[A-Za-z]:\\31309(?:\\|$)", re.IGNORECASE
            ),
            "household notification entity": re.compile(
                re.escape("notify." + "primary_phone")
            ),
            "household media-player entity": re.compile(
                re.escape("media_player." + "wo_shi")
            ),
        }
        ignored_parts = {".git", ".venv", ".ruff_cache", "__pycache__"}
        source_files = sorted(
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and not ignored_parts.intersection(path.relative_to(ROOT).parts)
            and path.suffix.lower()
            in {".py", ".json", ".yaml", ".yml", ".md", ".toml"}
        )
        for path in source_files:
            text = path.read_text(encoding="utf-8")
            for label, pattern in forbidden_patterns.items():
                with self.subTest(path=path, pattern=label):
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
