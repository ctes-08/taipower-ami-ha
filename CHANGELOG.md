# Changelog

## 0.1.0-alpha.1

First public alpha for HACS custom-repository installation and manual
Windows-to-Home-Assistant handoff testing.

- Adds the Taipower AMI config flow, energy sensors, status diagnostics, and a
  manual refresh button.
- Reads the existing relative credential handoff file without storing account
  passwords in Home Assistant.
- Keeps the Windows companion as a separate installation and release.
- Validates the integration against Home Assistant 2025.12.0 and 2026.8.3.
- Sends no maintainer telemetry or analytics.
