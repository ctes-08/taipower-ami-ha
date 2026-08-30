# Privacy policy

## Scope

This policy covers the Taipower AMI custom integration for Home Assistant. The
separate Windows Companion has its own repository and policy. This integration
has no project-operated server, telemetry, analytics, advertising, or crash
report upload.

## Data processed

The integration reads the operator-selected `credentials.json` file from
inside the Home Assistant configuration directory. That file contains the
minimum browser-created handoff values required by the official Taipower AMI
frontend: a `SESSION` value, an AMI identifier (`enkey`), and import timing
metadata. It does not contain or accept the Taipower account name, password,
CAPTCHA, or Cloudflare Turnstile response.

The credential path is stored in the Home Assistant config entry. Absolute
paths, paths outside the Home Assistant configuration directory, and symbolic
link traversal are rejected. The secret values remain in the handoff file and
are loaded only for requests; they are not copied into the config entry,
diagnostics, logs, or the integration's summary storage.

## Network destinations

At the configured interval or after an explicit manual refresh, the integration
sends HTTPS GET requests only to five fixed read-only AMI endpoints under
`https://service.taipower.com.tw/ebpps2/amichart/api/`: `fifteenlist`,
`daylist`, `monthlist`, `yearlist`, and `dayanddayalist`. The AMI identifier is
sent as the official endpoint parameter and `SESSION` as the official cookie.
Redirects are rejected. The client disables ambient proxy discovery so the
request destination cannot be changed by a process-level proxy setting.

No data is sent to the project maintainer or to a project-controlled service.
Taipower is a third-party service with its own terms and privacy practices.

## Local storage and retention

Home Assistant entities contain derived energy values and status. Home
Assistant may retain their state history according to the operator's Recorder
configuration and backups. The integration also stores a private, compact
summary containing refresh times, row counts, and derived totals. It does not
store raw response bodies, response rows, `SESSION`, `enkey`, or the credential
file path in that summary.

Removing the integration removes its config entry but does not currently claim
to erase the integration-managed summary from Home Assistant's private storage.
It also deliberately does not delete the credential handoff file, Home
Assistant Recorder history, or backups, because those are separately managed
by the operator. An operator who requires physical erasure must review Home
Assistant storage and backups separately.

## Operator control

The operator controls the polling interval, may disable or remove the config
entry, and may delete or replace the handoff file. Do not upload a credential
file, HAR, Home Assistant backup, browser profile, or unreviewed diagnostics.
Security reports must follow [SECURITY.md](SECURITY.md).
