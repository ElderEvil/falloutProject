# Issue #1392 — desktop scope and remaining work

[Issue #1392](https://github.com/ElderEvil/falloutProject/issues/1392) remains open
until installed-app and updater acceptance have evidence. Current setup, behavior,
validation, and rollout gates live in [DESKTOP.md](../frontend/DESKTOP.md).

## Scope and estimate

The first target is Linux x86_64 with shared gameplay code, password login,
`.deb`/AppImage packages, window state, tray alerts, and external links.
The original 2026-11-11 estimate for a release was 28–44 engineering hours
(roughly 4–6 days): shell/connectivity 6–10, native behavior 8–12,
CI/release/updater 8–12, and installed-app/upgrade validation 6–10.
Desktop OAuth adds an estimated 12–24 hours. These estimates exclude waiting for
credentials, deployment, releases, or test machines; a prototype is not release
acceptance. Windows/macOS and mobile follow separately.

## Remaining release requirements

1. Roll out the explicit production CORS origins, preserving the website origin.
   Validate installed-app authentication/session expiry, vault/media, chat WS,
   SSE/reconnect, external links, and notification icon. Derive CSP from actual
   production API/media URLs; do not grant wildcard network or remote IPC access.
2. Call the reusable desktop workflow after semantic-release publishes. Check out
   its exact release tag and attach packages to that existing release; keep
   desktop failures independent of server image builds. `GITHUB_TOKEN` tag pushes
   may not trigger another workflow. Keep frontend/package.json as version authority.
3. Provision updater signing secrets and recovery, retain the public key in app
   configuration, and publish signed artifacts plus `latest.json` over HTTPS.
   Provide an update/restart decision and recoverable download failures. Rehearse
   an installed-version upgrade, rejected signatures, network failure, and login
   persistence across updates. Updater signing is required even if OS signing is optional.
4. If desktop OAuth is added, design a single-use handoff with validated state and
   a deep-link/loopback return flow. Browser-cookie-bound web handoffs and simply
   opening a browser are insufficient; never put bearer tokens in deep links or
   allow arbitrary callback origins. Keep unsupported desktop actions unavailable.

Preserve existing progression pop-ups/toasts and bell entries, one subscription/
deduplication owner, and session/vault isolation. Permission denial must preserve
in-app delivery. Alerts after Quit require a separate push/background design.
