from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "taipower_ami"

IGNORED_PARTS = {".git", ".venv", ".ruff_cache", "__pycache__"}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {".gitattributes", ".gitignore"}


def _translation_paths(
    value: object, prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    if isinstance(value, dict):
        result: set[tuple[str, ...]] = set()
        for key, child in value.items():
            result.update(_translation_paths(child, (*prefix, key)))
        return result
    return {prefix}


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
        and (path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES)
    )


class RepositoryContractTests(unittest.TestCase):
    def test_required_publication_files_exist(self):
        required = {
            ROOT / ".gitattributes",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
            ROOT / ".github" / "workflows" / "validate.yml",
            ROOT / "README.md",
            ROOT / "SECURITY.md",
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
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "zh-Hant.json",
            INTEGRATION / "diagnostics.py",
            ROOT / "tests" / "conftest.py",
            ROOT / "tests" / "ha_lifecycle.py",
        }
        self.assertEqual(
            [], sorted(str(path) for path in required if not path.is_file())
        )
        self.assertFalse(
            (INTEGRATION / "strings.json").exists(),
            "Custom integrations must ship runtime English in translations/en.json",
        )

    def test_manifest_keeps_alpha_identity_and_neutral_owner_placeholder(self):
        manifest = json.loads(
            (INTEGRATION / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["domain"], "taipower_ami")
        self.assertEqual(manifest["name"], "Taipower AMI")
        self.assertEqual(
            manifest["documentation"], "https://github.com/OWNER/taipower-ami-ha"
        )
        self.assertEqual(manifest["codeowners"], ["@OWNER"])
        self.assertNotIn("issue_tracker", manifest)
        self.assertEqual(manifest["integration_type"], "service")
        self.assertEqual(manifest["iot_class"], "cloud_polling")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["requirements"], [])
        self.assertIn("alpha", manifest["version"])

    def test_english_and_traditional_chinese_translation_keys_match(self):
        translations = INTEGRATION / "translations"
        english = json.loads((translations / "en.json").read_text(encoding="utf-8"))
        traditional_chinese = json.loads(
            (translations / "zh-Hant.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            _translation_paths(english),
            _translation_paths(traditional_chinese),
        )
        for language, document in {
            "en": english,
            "zh-Hant": traditional_chinese,
        }.items():
            for path in _translation_paths(document):
                value: object = document
                for key in path:
                    value = value[key]  # type: ignore[index]
                with self.subTest(language=language, key=".".join(path)):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip())

    def test_service_metadata_lives_in_translations(self):
        service_yaml = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        self.assertIn("refresh_data:", service_yaml)
        self.assertIn("fields:", service_yaml)
        self.assertIn("entry_id:", service_yaml)
        self.assertIn("selector:", service_yaml)
        self.assertNotRegex(service_yaml, r"(?m)^\s+(?:name|description):")

    def test_workflow_actions_are_commit_pinned(self):
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        action_references = re.findall(r"\buses:\s*[^@\s]+@([^\s#]+)", workflow)
        self.assertGreaterEqual(len(action_references), 5)
        for reference in action_references:
            with self.subTest(reference=reference):
                self.assertRegex(reference, r"\A[0-9a-f]{40}\Z")
        checkout_count = workflow.count("uses: actions/checkout@")
        self.assertGreater(checkout_count, 0)
        self.assertEqual(
            checkout_count,
            workflow.count("persist-credentials: false"),
        )

    def test_home_assistant_lifecycle_matrix_is_pinned(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
        self.assertEqual(
            hacs,
            {
                "name": "Taipower AMI",
                "country": "TW",
                "homeassistant": "2025.12.0",
            },
        )
        self.assertEqual(
            project["project"]["optional-dependencies"]["test"],
            ["pytest==9.0.3", "ruff==0.16.5"],
        )
        self.assertEqual(
            project["project"]["optional-dependencies"]["ha-test"],
            [
                "homeassistant==2026.8.3",
                "pytest-homeassistant-custom-component==0.13.357",
            ],
        )
        self.assertEqual(
            project["project"]["optional-dependencies"]["ha-test-minimum"],
            [
                f"homeassistant=={hacs['homeassistant']}",
                "pytest-homeassistant-custom-component==0.13.298",
                "pycares==4.11.0",
            ],
        )
        self.assertEqual(
            project["tool"]["pytest"]["ini_options"]["asyncio_mode"], "auto"
        )

        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('ha_version: "2025.12.0 minimum"', workflow)
        self.assertIn('ha_version: "2026.8.3 stable"', workflow)
        self.assertIn('python: "3.13"', workflow)
        self.assertIn('python: "3.14"', workflow)
        self.assertIn("extra: ha-test-minimum", workflow)
        self.assertIn("extra: ha-test", workflow)
        self.assertIn("python -m pytest tests/ha_lifecycle.py", workflow)

    def test_public_tree_contains_no_sensitive_filenames(self):
        forbidden_names = {
            ".env",
            "cookies.json",
            "cookies.txt",
            "credentials.json",
            "secrets.yaml",
            "session.json",
            "token.json",
        }
        forbidden_suffixes = {
            ".har",
            ".key",
            ".p12",
            ".pem",
            ".pfx",
            ".sqlite",
            ".sqlite3",
            ".tar",
            ".tgz",
            ".zip",
        }
        violations: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if IGNORED_PARTS.intersection(relative.parts):
                continue
            lowered = path.name.lower()
            if lowered in forbidden_names or any(
                lowered.endswith(suffix) for suffix in forbidden_suffixes
            ):
                violations.append(str(relative))
        self.assertEqual([], violations)

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
                r"\b[A-Za-z]:\\" + re.escape("31" + "309") + r"(?:\\|$)",
                re.IGNORECASE,
            ),
            "UNC path": re.compile(
                r"(?<!\\)\\{2}[^\\\s]+\\[^\\\s]+", re.IGNORECASE
            ),
            "legacy publisher identifier": re.compile(
                re.escape("si" + "73"), re.IGNORECASE
            ),
            "legacy organization identifier": re.compile(
                re.escape("CT" + "ES"), re.IGNORECASE
            ),
            "household notification entity": re.compile(
                re.escape("notify." + "primary_phone")
            ),
            "household media-player entity": re.compile(
                re.escape("media_player." + "wo_shi")
            ),
            "GitHub access token": re.compile(
                r"\b(?:" + "gh" + r"[oprsu]_[A-Za-z0-9_]{20,}|"
                + "github" + r"_pat_[A-Za-z0-9_]{20,})\b"
            ),
            "private-key PEM block": re.compile(
                re.escape("-----BEGIN " + "PRIVATE KEY-----"), re.IGNORECASE
            ),
            "hard-coded bearer credential": re.compile(
                r"\b" + "Bear" + r"er\s+[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE
            ),
            "certificate identity": re.compile(
                r"(?:" + "thumb" + r"print|certificate[_ -]?fingerprint)"
                r"\s*[:=]\s*[0-9a-f]{40,64}",
                re.IGNORECASE,
            ),
        }
        email_pattern = re.compile(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE
        )
        credential_literal = re.compile(
            r"[\"'](?:session|enkey|token|password)[\"']\s*:\s*"
            r"[\"'](?P<value>[^\"']+)[\"']",
            re.IGNORECASE,
        )
        safe_test_prefixes = ("opaque_", "session_value_", "enkey_value_")

        for path in _source_files():
            text = path.read_text(encoding="utf-8")
            for label, pattern in forbidden_patterns.items():
                with self.subTest(path=path, pattern=label):
                    self.assertIsNone(pattern.search(text))

            with self.subTest(path=path, pattern="email address"):
                self.assertIsNone(email_pattern.search(text))

            for match in credential_literal.finditer(text):
                relative_parts = path.relative_to(ROOT).parts
                is_safe_fixture = (
                    "tests" in relative_parts
                    and match.group("value").startswith(safe_test_prefixes)
                )
                with self.subTest(path=path, pattern="credential literal"):
                    self.assertTrue(is_safe_fixture)


if __name__ == "__main__":
    unittest.main()
