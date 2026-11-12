# Issue #1392 — Tauri desktop implementation readiness

Prepared 2026-11-11 against checkout `d1f286ee` and the current issue description.
Source: https://github.com/ElderEvil/falloutProject/issues/1392

## Recommendation and estimate

Start with Linux x86_64, password authentication, `.deb` and `.AppImage`, native
notifications while running in the tray, window state, external links, and signed
updates. Keep gameplay services and stores shared with the web build. Mobile and
Windows/macOS distribution follow separately. Password-first is a proposed scope,
pending the maintainer's answer about desktop OAuth.

Engineering effort for one developer familiar with this repo:

| Work | Estimate |
| --- | --- |
| Tauri shell, build modes, origins, CSP, basic login/vault/chat | 6–10 hours |
| Native notifications, tray lifecycle, window state, external links | 8–12 hours |
| CI artifacts, semantic-release integration, signed updater | 8–12 hours |
| Installed-app validation, upgrade rehearsal, documentation | 6–10 hours |
| Linux release total, password-first | **28–44 hours / roughly 4–6 working days** |
| Desktop OAuth, if required initially | **additional 12–24 hours** |

A launchable prototype is plausible in one day. The issue's 1–1.5 days is too
small for all acceptance criteria, especially background delivery and a verified
upgrade. Estimates include implementation and validation, exclude waiting for
credentials, backend deployment, release availability and access to test machines.
Confidence is medium until the installed Linux shell has been exercised.

## Corrections to the issue assumptions

- The existing app uses REST, chat WebSocket, **and fetch-based SSE**. SSE lives in
  `frontend/src/core/composables/useEventStream.ts` and needs connection/reconnect
  validation in the webview.
- `useBackgroundActivity.ts` permits work only while the document is visible.
  Hidden-window notifications require an explicit desktop lifecycle policy.
  Preserve a single notification subscription and deduplication owner; do not
  keep all gameplay polling active merely to enable tray alerts.
- Native alerts need implementation: there is no existing OS notification sender.
  Plan to use Tauri's notification plugin and explicit permission handling rather
  than assume Web Notifications behavior across webviews. Preserve existing
  progression modals/toasts and bell entries.
- OAuth currently leaves the app through `window.location.assign`; backend
  callbacks return to `settings.FRONTEND_URL`, and handoff redemption is bound to
  a browser cookie. Opening the system browser alone does not return credentials
  to the desktop webview. Full desktop OAuth needs a designed, single-use handoff
  and deep-link/loopback return flow with state validation; never put bearer
  tokens in deep links. Do not simply allow arbitrary callback origins.
- Media origins cannot be established from `image.ts` alone. RustFS public URLs
  use `RUSTFS_PUBLIC_URL`, falling back to its endpoint. Confirm actual production
  response URLs before freezing CSP. Review fonts, audio, icons, blob/data URLs,
  and image normalization under a custom scheme too.
- CORS covers HTTP, including SSE, rather than WebSocket handshakes. The current
  chat route has token authentication and no explicit Origin check. Verify any
  proxy/security middleware separately; CORS changes alone do not govern chat.
- Adding app origins requires deploying backend configuration before a production
  desktop client works. Preparation/builds can leave deployment untouched; full
  production acceptance cannot promise that no configuration rollout is needed.
- Tauri v2 uses a top-level `identifier`, not `bundle.identifier`. Tray support is
  a Tauri core feature (`tray-icon`), rather than the proposed tray plugin.
- Updater signatures are mandatory even when OS package signing is optional.
  Keys and an actual installed-version-to-new-version rehearsal are prerequisites.

## Implementation sequence

1. **Prove the runtime boundary.** Add `frontend/src-tauri/` with Rust sources,
   Cargo manifest/lock, Tauri configuration, minimal local capabilities and icons.
   Add frontend-local CLI/scripts and a desktop build mode with an explicit API
   URL. Use the existing Vite+ production build and `dist` directory. Avoid the
   normal dev script's automatic local OpenAPI generation for a prod-backed
   desktop session; preserve the web development workflow. Pin the desktop dev
   port with strict-port behavior. No root npm manifest.
2. **Validate connectivity and content.** Add explicit desktop origins to backend
   CORS configuration, preserving existing browser origins and environment
   overrides. Use a distinct development CSP for local Vite/HMR. Establish the
   production CSP from actual network requests; no wildcard network or remote
   IPC permissions. Check password login, refresh rotation, sign-out/session
   expiry navigation, vault load, SSE, chat and media in an installed artifact.
   Audit WebKit syntax support because the Vite build currently targets `esnext`.
3. **Integrate native behavior.** Add a thin desktop runtime boundary, loaded only
   for Tauri. Wire notifications into existing event delivery/deduplication;
   permission denial must not break in-app delivery. Keep notification delivery
   alive when hidden without duplicating subscriptions or resuming all polling.
   Specify hide-to-tray, Show and Quit behavior, and restore window bounds.
   Permit external HTTP(S) links through the opener. If password-first is chosen,
   make unsupported OAuth actions explicitly unavailable in the desktop UI.
4. **Build and release.** Add a reusable/manual desktop workflow; call it after
   semantic-release publishes using the existing release job outputs. Checkout
   the exact release tag and upload to that existing release. Do not rely solely
   on a tag-push workflow: releases created with `GITHUB_TOKEN` may not trigger
   another workflow. Keep desktop failures independent of server image builds.
   Derive desktop version from the released frontend version; do not create a
   second version authority. Produce signed updater artifacts and `latest.json`
   only for successful builds, with stable names and an HTTPS endpoint. Provide
   a user-visible update/restart decision and recoverable download failures.
5. **Rehearse delivery.** Install both Linux package formats, validate runtime
   dependencies and tray behavior on the intended desktop environments, and
   perform a real signed update between two distinct versions. Document local
   toolchains, signing-secret setup, packaging and recovery.

Suggested review boundaries: shell/connectivity; native behavior; release/updater.
The shell can be reviewed before all release credentials are available, but the
issue stays open until installed-app and updater acceptance have evidence.

## Prerequisites and decisions

- Confirm whether the initial desktop version requires Google/GitHub OAuth.
- Confirm Linux x86_64 first and identify installed-app test hosts. Rust/Cargo
  were not found on PATH here, and the WebKitGTK pkg-config probe did not resolve;
  use the documented Arch host or a build container/CI runner. No tools installed
  during this preparation.
- Confirm public API/media hosts and arrange the production CORS configuration
  rollout. The checked-in storage fallback is not evidence of the live host.
- Provision the updater signing key/password as GitHub secrets, retain its public
  key in app config, and arrange secure recovery of the private key.
- Confirm alert scope: proposed behavior is notifications while the process runs,
  including hidden-to-tray; alerts after Quit need a separate push/background
  design. Confirm whether hiding should be the default close-button behavior.

## Acceptance evidence

- Backend CORS preflight and authenticated HTTP work for actual desktop origins;
  normal web behavior remains covered.
- Installed `.deb` and `.AppImage`: password login, restart persistence, refresh,
  expiry/sign-out navigation, vault, images/audio, chat WS, SSE and reconnect.
- Hidden-to-tray event produces one OS alert; reopening/reconnecting does not
  repeat it. Account/vault switches cannot deliver stale alerts. Denied permission
  preserves in-app alerts. Quit ends subscriptions and the process.
- Window state restores sensibly; external links open in the browser.
- Release assets match the semantic-release version/tag. A signed upgrade between
  two installed versions succeeds; invalid signatures and network failures fail
  without corrupting the installed app. Retest persisted login after upgrading.
- Run focused tests for changed lifecycle/delivery boundaries, frontend checks,
  Rust formatting/checks, and CI package builds. Manual installed-artifact testing
  remains necessary for OS notifications, tray behavior and updates.

## Reference documentation

- Tauri configuration: https://v2.tauri.app/reference/config/
- Notifications: https://v2.tauri.app/plugin/notification/
- Tray: https://v2.tauri.app/learn/system-tray/
- Updater and signing: https://v2.tauri.app/plugin/updater/
- GitHub release pipeline: https://v2.tauri.app/distribute/pipelines/github/

This is implementation preparation only. No application, toolchain, deployment,
GitHub issue, or release configuration was changed.
