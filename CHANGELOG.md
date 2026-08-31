# Changelog

## 0.1.0-alpha.2

- Restores verified HTTPS access on Python 3.14 when Taipower serves its legacy
  TWCA certificate chain. Only OpenSSL strict RFC 5280 mode is relaxed; CA,
  hostname, validity-period, and signature verification remain enabled.
- Classifies TLS, DNS, timeout, and general connection failures without
  exposing raw URLs, credentials, or exception details.

## 0.1.0-alpha.1

First public alpha for HACS custom-repository installation and manual
Windows-to-Home-Assistant handoff testing.

- Adds the Taipower AMI config flow, energy sensors, status diagnostics, and a
  manual refresh button.
- Reads the existing relative credential handoff file without storing account
  passwords in Home Assistant.
- Keeps the Windows companion in a separate repository and release channel.
- Validates the integration against Home Assistant 2025.12.0 and 2026.8.3.
- Sends no maintainer telemetry or analytics.
