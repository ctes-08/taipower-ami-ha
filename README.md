# Taipower AMI for Home Assistant

> **Alpha software.** This repository is an early, unofficial Home Assistant
> custom integration. It is not affiliated with or endorsed by Taiwan Power
> Company. Do not use its values as the authoritative source for billing.

This repository is the Home Assistant half of a two-part design:

1. **This HACS/custom integration** reads a minimal credential handoff file,
   calls five existing AMI endpoints with GET requests, and publishes compact
   sensors.
2. **A separate Windows companion** performs the user-initiated browser
   handoff after a normal Taipower login. HACS cannot install or update that
   Windows program.

The integration does not automate login, solve or bypass Cloudflare Turnstile,
store an account password, or scan Taipower endpoints.

## Alpha scope

The current implementation preserves the data meanings of these five
read-only endpoints:

| Endpoint | Meaning retained by the client |
| --- | --- |
| `fifteenlist` | 15-minute energy; missing or unavailable history is not converted to zero |
| `daylist` | hourly tariff-period columns and total |
| `monthlist` | daily tariff-period columns and total |
| `yearlist` | monthly tariff-period columns and total |
| `dayanddayalist` | first-date and second-date comparison columns |

It currently exposes the latest 15-minute value, today/month/year summaries,
a today-versus-yesterday delta, a sanitized status sensor, a refresh button,
and the `taipower_ami.refresh_data` service.

This alpha **does not yet reproduce the private deployment's permanent SQLite
history, long-range charts, tariff analysis, voice announcements, phone
notifications, HASS.Agent automation, or dashboard**. It stores only a small,
credential-free summary of the last successful refresh.

## Credential handoff

The default file is:

```text
/config/.taipower_ami/credentials.json
```

The setup form accepts a path relative to the Home Assistant configuration
directory. Absolute paths, paths outside the configuration directory, and
symbolic-link targets are rejected. The file is produced by the separate
Windows companion and contains only the handoff format version, `SESSION`, AMI
identifier, and import timestamps. Never upload that file, a HAR, a browser
profile, or diagnostic output that has not been reviewed.

All file and HTTP work runs in Home Assistant's executor. The event loop does
not perform synchronous disk or network I/O.

## Local alpha installation

Until a public release exists, copy this directory into a test Home Assistant
instance:

```text
custom_components/taipower_ami
```

Restart Home Assistant, then add **Taipower AMI** from
**Settings > Devices & services**. Complete the Windows handoff before opening
the setup form.

The default polling interval is 120 minutes and the accepted range is 60 to
1440 minutes. Manual refresh remains available from the entity button or the
service. Avoid setting up external automations that repeatedly call the
service.

## HACS publication status

This source tree has HACS-compatible placement, but it is not publication-ready
yet. English runtime text is now shipped in `translations/en.json`, and private
staging CI runs unit tests, Ruff, the repository privacy contract, a
socket-blocked Home Assistant 2026.8.3 lifecycle test, and Home Assistant
`hassfest`.

The remaining gates before the first public release are:

- select and add a public-source license;
- replace the neutral `OWNER` placeholder in `manifest.json`, add the final
  GitHub code owner and issue URL, and rerun the neutrality contract. The
  current staging account handle conflicts with that contract and therefore is
  intentionally not embedded in tracked public source. The temporary
  `@OWNER` codeowner exists only to exercise the complete hassfest schema while
  the repository remains private;
- make the reviewed repository public, then enable and pass the official HACS
  validation action;
- complete a manual Windows-to-Home-Assistant handoff smoke test in a
  disposable instance. CI already exercises setup, refresh, reauthentication,
  unload, removal, re-add, and diagnostics with fake data and all non-local
  sockets blocked;
- publish the Windows companion separately and keep its unsigned or signed
  release artifacts and checksums outside this HACS repository.

HACS requires a public GitHub repository for normal distribution. A private
remote is useful for CI and review, but functional testing during that phase
must use a local copy of `custom_components/taipower_ami`. HACS validation is
intentionally not enabled while this repository is private and has no selected
license; it must be added and pass after both gates are satisfied.

No open-source license has been selected yet. Until a license is added, the
repository contents are not offered under an open-source license.

## Development

Pure parser/client tests do not require Home Assistant:

```powershell
python -m compileall -q custom_components tests
ruff check .
python -m unittest discover -s tests -v
```

The real Home Assistant lifecycle test requires Linux, Python 3.14.2 or newer,
and a separate dependency set pinned to the stable Home Assistant release:

```bash
python -m pip install ".[ha-test]"
python -m pytest tests/ha_lifecycle.py
```

The package can be installed on Windows, but Home Assistant's test runner uses
the POSIX-only `fcntl` module. The Ubuntu CI job is therefore the authoritative
lifecycle result; Windows remains suitable for the fast parser and contract
tests above.

The Home Assistant pytest plugin disables non-local sockets for every lifecycle
test. The Taipower fetch function is also replaced with deterministic fake
snapshots, and the disposable credential file contains test-only opaque values.

The client is synchronous by design because it uses Python's standard-library
HTTP stack. Home Assistant calls it only through `async_add_executor_job`.

CI actions are pinned to full commit hashes. The weekly scheduled run provides
an additional signal for upstream `hassfest` changes; it does not replace the
disposable Home Assistant validation gate.

## Security and privacy

- No account password or CAPTCHA material is accepted.
- Redirects and non-JSON responses are treated as authentication failures.
- Only the official HTTPS host and fixed AMI API paths are used.
- Errors and diagnostics contain no `SESSION`, AMI identifier, cookies, or raw
  response bodies.
- No household entity names, LAN addresses, UNC paths, notification services,
  personal email addresses, or signing identities belong in this repository.

Follow [SECURITY.md](SECURITY.md) for private reporting. Do not open a public
issue containing credentials or a captured browser session.
