# Taipower AMI for Home Assistant

> **Alpha software.** This repository is an early, unofficial Home Assistant
> custom integration. It is not affiliated with or endorsed by Taiwan Power
> Company. Do not use its values as the authoritative source for billing.

This repository is the Home Assistant half of a two-part design:

1. **This HACS/custom integration** reads a minimal credential handoff file,
   calls five existing AMI endpoints with GET requests, and publishes compact
   sensors.
2. **The separate
   [Windows companion](https://github.com/ctes-08/taipower-ami-windows)**
   performs the user-initiated browser handoff after a normal Taipower login.
   HACS cannot install or update that Windows program.

Install the companion only from a supported Release in its own repository.
The companion repository is public, but it does not currently have a supported
public binary Release; a source checkout is not an approved installer.

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

## Manual alpha installation

For local development or a manual test installation, copy the repository's
`custom_components/taipower_ami` directory to this exact destination in the
Home Assistant instance:

```text
/config/custom_components/taipower_ami/
```

Restart Home Assistant, then add **Taipower AMI** from
**Settings > Devices & services**. Complete the Windows handoff before opening
the setup form.

The default polling interval is 120 minutes and the accepted range is 60 to
1440 minutes. Manual refresh remains available from the entity button or the
service. Avoid setting up external automations that repeatedly call the
service.

## Public installation with HACS

This repository is public, so users can install it without waiting for
default-store approval. HACS installs only the Home Assistant half; the
separate Windows companion remains a prerequisite and follows its own release
process.

1. In HACS, open the three-dot menu and select **Custom repositories**.
2. Add `https://github.com/ctes-08/taipower-ami-ha` as an **Integration**.
3. Find **Taipower AMI**, download it, restart Home Assistant, and add the
   integration from **Settings > Devices & services**.

That custom-repository route does not require an application to HACS. Inclusion
in HACS's default repository list is a separate, later review. It requires a
public repository, successful HACS and `hassfest` Actions without ignored
checks, and a full GitHub Release created after those checks pass. Default-list
review is not a prerequisite for installing this project as a custom
repository.

## HACS publication status

This repository is public and has passed the configured official HACS and Home
Assistant `hassfest` validation jobs. CI also runs unit tests, Ruff, the
repository privacy contract, and socket-blocked lifecycle tests against both
the declared minimum Home Assistant 2025.12.0 release and the reviewed stable
Home Assistant 2026.8.3 release.

The latest published version, `0.1.0-alpha.2`, remains an alpha intended for
HACS custom-repository installation and Windows-to-Home-Assistant handoff smoke
testing. CI exercises setup, refresh, reauthentication, unload, removal,
re-add, and diagnostics with fake data and all non-local sockets blocked. The
Windows companion is maintained in a separate repository and release channel;
its unsigned or signed artifacts and checksums do not belong in this HACS
repository.

After every HACS update, restart Home Assistant before judging the result.
Users upgrading from `0.1.0-alpha.1` must install `0.1.0-alpha.2` or newer to
receive the Python 3.14 TLS compatibility fix.

The HACS metadata identifies this Taiwan-only service with `country: TW` and
declares Home Assistant 2025.12.0 as its minimum supported release. Both that
minimum and the reviewed stable release are exercised by the isolated lifecycle
matrix. Only keys documented by the current HACS manifest specification are
kept in `hacs.json`.

The official HACS job runs for this public repository, is pinned to a reviewed
action commit, and has no ignored checks. Both the default branch and published
release tags must pass it alongside `hassfest`, the repository contract, unit
tests, and the supported Home Assistant lifecycle matrix.

## Development

Pure parser/client tests do not require Home Assistant:

```powershell
python -m compileall -q custom_components tests
ruff check .
python -m unittest discover -s tests -v
```

The real Home Assistant lifecycle test requires Linux and a separate virtual
environment for each pinned runtime. The declared minimum uses Python 3.13 and
Home Assistant 2025.12.0:

```bash
python -m pip install . \
  "homeassistant==2025.12.0" \
  "pytest-homeassistant-custom-component==0.13.298" \
  "pycares==4.11.0"
python -m pytest tests/ha_lifecycle.py
```

The historical minimum runtime is installed directly only in the isolated
compatibility job; it is not declared as an installable project dependency and
is never shipped to users. The job pins `pycares` to the last compatible 4.x
release because Home Assistant 2025.12.0 pins `aiodns` 3.5.0, whose broad
dependency range otherwise permits an incompatible newer `pycares` API. The
stable-runtime extra intentionally keeps its own newer dependency set.

The reviewed stable runtime uses Python 3.14.2 or newer and Home Assistant
2026.8.3:

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
- Redirects, HTTP 401, and HTTP 403 are treated as authentication failures;
  non-JSON responses are rejected as temporary connection or service failures.
- Only the official HTTPS host and fixed AMI API paths are used.
- Python 3.14 compatibility clears only OpenSSL's `VERIFY_X509_STRICT` flag for
  Taipower's legacy TWCA chain. CA trust, hostname, validity-period, and
  signature verification remain enabled.
- Errors and diagnostics contain no `SESSION`, AMI identifier, cookies, or raw
  response bodies.
- No household entity names, LAN addresses, UNC paths, notification services,
  personal email addresses, or signing identities belong in this repository.

Follow [SECURITY.md](SECURITY.md) for private reporting. Do not open a public
issue containing credentials or a captured browser session.

The complete data flow, local retention boundary, and operator controls are
documented in [PRIVACY.md](PRIVACY.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
