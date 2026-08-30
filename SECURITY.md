# Security policy

## Reporting a vulnerability

Do not include security details in a public issue. After this repository is
public, use **Security > Report a vulnerability** on GitHub to start a private
security advisory. If private vulnerability reporting is not available, open
only a minimal issue asking the maintainer to enable a private reporting
channel; do not include reproduction details in that issue.

Never upload or paste any of the following:

- `credentials.json`, a HAR, browser cookies, a browser profile, or a Home
  Assistant backup;
- a Taipower `SESSION`, AMI identifier, account number, electric number,
  password, CAPTCHA or Turnstile material;
- Home Assistant secrets, access tokens, private URLs, LAN addresses, UNC
  paths, signing certificates, or certificate fingerprints;
- unreviewed diagnostics, traces, screenshots, or logs that may contain any of
  the above.

Provide only the minimum redacted reproduction steps, affected version, Home
Assistant version, and expected versus observed behavior. The integration's
diagnostics are designed to omit credential material, but review exported
diagnostics before sharing them.

## Supported versions

This project is alpha software. Security fixes are made only on the current
default branch and, after releases exist, the latest published release. Older
commits and unreleased local builds are not supported.

## Scope

Reports about this integration or its published packaging are in scope. Do not
probe, scan, stress, or attempt to bypass authentication on Taipower or any
other third-party system while investigating a report.
