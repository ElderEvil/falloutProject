# Tauri desktop — implementation progress

This wave adds a Linux desktop shell around the existing frontend. Gameplay code
is shared. OAuth return flow, signed updates and release automation remain later
waves. The supplied vault/lightning image in `frontend/src-tauri/app-icon.png` is
the current icon source. The Redis transport bridge described below delivers worker events to API SSE
clients. Native alerts were visually confirmed in development. A local AppImage
is available for testing; production login remains gated on the CORS deployment.

## Bazzite development environment

The dedicated `fallout-tauri-nvidia` Distrobox uses Ubuntu 24.04 with its own home at
`~/.local/share/fallout-tauri/home`. It contains Rust, Node 22.22.3, pnpm 11.9.0,
and the GTK/WebKit development packages from the
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

Container builds use a separate Git worktree to keep native dependencies and
`node_modules` independent of the host checkout:

```bash
distrobox enter fallout-tauri-nvidia
cd /var/home/elder/Projects/falloutProject-tauri/frontend
pnpm install --frozen-lockfile
pnpm run desktop:dev
```

The desktop dev server uses port 5173 and fails if it is occupied. It skips the
normal web dev script's local OpenAPI generation. Run `pnpm run types:generate`
against a local backend when API schemas change.

```bash
# Build the frontend and native binary without packaging installers
pnpm run desktop:build --debug --no-bundle

# Build the configured Linux installers (later distribution validation)
pnpm run desktop:build
```

Tauri reads the app version from `frontend/package.json`, which Semantic Release
already owns. The Rust crate's `0.0.0` is internal, non-published metadata.
`Cargo.lock` records native dependencies.

## API connectivity and rollout gate

`.env.desktop` selects `https://fallout-api.evillab.tech`. A local dev session can
override it with `VITE_API_BASE_URL=http://localhost:8000 pnpm run desktop:dev`.
Production CSP allows the production API; development CSP also permits the local
API and Vite HMR. Custom deployments need a matching CSP configuration.

The local backend default CORS list includes `tauri://localhost`,
`http://tauri.localhost`, and `https://tauri.localhost`. An explicit deployment
override of `BACKEND_CORS_ORIGINS` replaces defaults: preserve its existing web
origins and add these desktop origins during rollout.

The k3s backend manifest explicitly overrides that setting. Its allowlist now
preserves the production website and includes all three desktop origins; the
manifest must be rolled out for production to use them. A regression exercises
preflights against the manifest's actual allowlist, including an untrusted origin.

On 2026-11-12 the production API returned `400 Disallowed CORS origin` to a desktop
preflight. The configuration must be deployed before installed-app production
login can pass. This wave does not deploy or modify production configuration.
WebSocket handshakes require separate validation; HTTP CORS does not govern them.

Before proceeding beyond the shell, verify actual production storage/media hosts
against CSP and decide whether desktop OAuth is required initially. Existing
OAuth navigates out to a browser flow and is not yet a supported desktop flow.

## Wave 1 validation (2026-11-12)

- Frozen frontend dependency install passes inside the isolated worktree.
- `pnpm run desktop:bundle` and `pnpm run desktop:build --debug --no-bundle` pass.
  The native executable is `frontend/src-tauri/target/debug/fallout-desktop`;
  its dynamic libraries resolve inside Distrobox. GUI login and installed-package
  behavior have not been validated.
- `cargo check`, Rust formatting, changed frontend config lint/format checks,
  and Python lint/format/type checks for the changed config pass.
- The four desktop CORS preflight tests pass, including an untrusted-origin
  rejection case. Run them with `uv run pytest app/tests/test_api/test_desktop_cors.py`.
- The dependency install reports the existing `openapi-typescript` TypeScript 5
  peer range against this repo's TypeScript 6 baseline. Tauri adds no new peer
  conflict; this wave does not change that existing dependency policy.

Paused before production connectivity validation: the backend CORS rollout is
required. No backend deployment, pushes or release publication were performed.

## NVIDIA validation (2026-11-12)

The original container lacked NVIDIA integration and WebKit used llvmpipe software
rendering. Its replacement was created by cloning the stopped `fallout-tauri`
container with Distrobox's `--nvidia` option, preserving the toolchain, isolated
home and project mount. Use `fallout-tauri-nvidia` for subsequent sessions. The
original container is retained, stopped, as a fallback.

The relaunched app and WebKit renderer both load `libEGL_nvidia` and
`libnvidia-eglcore`, with zero llvmpipe threads. Three-second live samples:

| Renderer metric | Original container | NVIDIA-enabled container |
| --- | --- | --- |
| CPU (100% = one core) | 484.6% | 16.6% |
| Resident memory | 1832.8 MiB | 577.2 MiB |
| llvmpipe threads | 16 | 0 |

These samples were taken at different moments in the live app, not under an
identical replayed workload. They establish removal of software rendering, not a
controlled performance improvement percentage. Resource snapshots are available
locally at `/tmp/fallout-desktop-performance.json` and
`/tmp/fallout-desktop-performance-nvidia.json`.

Local desktop development currently uses the ignored `.env.desktop.local` override
in both worktrees, with `VITE_API_BASE_URL=http://localhost:8000`. The local backend
is independent of the Distrobox and remains running on the host.

## Wave 2a — window state and tray

Window size, position (where supported by the window system), and maximized state
are saved and restored by the native window-state plugin. Visibility is excluded
from restoration so the app opens visibly even after quitting from the tray.

Closing the main window hides it after successful tray creation. The tray menu's
**Show Fallout Shelter** action restores and focuses the window; **Quit** exits
the app. If tray creation or hiding fails, close keeps its normal exit behavior.
Native background notifications are integrated in wave 2b below.

Validation: locked Cargo check and Rust formatting pass. The running app registered
with KDE's StatusNotifierWatcher; its menu exposes Show/Quit. Both menu actions
were invoked through the session bus, Quit terminated the process, and the window
state file was written successfully. The maintainer confirmed the tray works.

## Wave 2b — native integration and cross-process delivery

The existing notification SSE connection opts into remaining open while the
desktop window is hidden. Other subscriptions and gameplay polling retain their
visibility-based pausing. Native alerts are emitted from the bell's existing
deduplication path, for the active vault, with session/token/vault and visibility
checks repeated after asynchronous permission lookup. Permission denial preserves
in-app delivery. Only locally loaded main-window code has notification and scoped
HTTP(S) opener capabilities; no filesystem opener permission is granted.

External HTTP(S) anchor links open through the OS browser. The explicit changelog
link uses the same helper; ordinary browser builds retain browser behavior.
OAuth navigation is not a supported desktop return flow yet. Provider sign-in on
login/registration and provider linking in profile settings are hidden in desktop
mode; browser OAuth and management of existing connections remain available.
Regression tests reproduce both unsupported desktop entry points before the fix;
64 focused auth/profile/desktop tests and frontend typechecking pass afterward.

The supplied 1024px logo has been converted into the configured native icon sizes
with the Tauri icon CLI. Original source and generated desktop assets are kept
together. Runtime packages `kde-config-gtk-style`, `appmenu-gtk3-module`,
`gstreamer1.0-plugins-bad`, and `gstreamer1.0-tools` were installed in the NVIDIA
container. Both `fakevideosink` and `webvttenc` resolve; the relaunch log no longer
shows the previously reported missing-module/media warnings.

Validation: 78 focused frontend tests pass, covering notification deduplication,
permission denial/failure, saved vault selection before hydration, delayed session/window changes, hidden SSE, and session
expiry. Changed frontend lint/format, frontend typecheck/build, locked native
Cargo check and Rust formatting pass. The maintainer confirmed a real exploration
alert appeared as an OS notification while the app was hidden in the tray.

The API now starts the existing Redis broadcast listener in its lifespan, even
without a WebSocket connection. Remote personal notification messages are relayed
into local notification SSE queues; sender-instance filtering suppresses echoes.
Worker publishing uses a short-lived client owned by the current call, avoiding a
shared listener/pool bound to a different Dramatiq thread's event loop.

Redis disconnection/resubscription closes notification SSE queues so clients
reconnect and reload persisted notifications. Other SSE topics remain connected.
Listener cancellation unsubscribes and closes resources. Redis Pub/Sub is still
best-effort, not a durable event log; catch-up uses the existing recent-inbox path.
Notification database writes and post-commit/deferred delivery ownership are unchanged.

A regression reproduced the worker-to-API gap before the fix. The relevant backend
suite passes 78 tests, including reconnect/cleanup, sender echo suppression,
malformed/unrelated-message rejection, user isolation, notification/API behavior,
WebSocket authentication, and architecture guards. A separate publishing process
using the real local Redis server reached an authenticated SSE connection on the
running API. Local API and worker are using the updated code. Native delivery was
visually confirmed; the notification icon is missing in the current development
launch and still needs verification with desktop integration. No production changes
or pushes have been made.


## Wave 3 — Linux packaging (2026-11-12)

Native notifications now resolve an explicit bundled `notification-icon.png`
through Tauri's resource API. This replaces the executable-name icon lookup that
left development alerts iconless in KDE. The resource is copied from the existing
128px app icon; no additional filesystem capability is required. The regression
failed before the fix; all 78 focused frontend tests, changed TypeScript lint and
format checks, and frontend typechecking pass. The icon resource is present in the
AppImage. Its appearance in an actual updated-app alert still needs visual verification.

Build from the isolated worktree, explicitly selecting the production API so an
ignored local environment override does not leak into the release artifact:

```bash
distrobox enter fallout-tauri-nvidia
cd /var/home/elder/Projects/falloutProject-tauri/frontend
VITE_API_BASE_URL=https://fallout-api.evillab.tech pnpm run desktop:build --bundles appimage
```

The optimized build and AppImage packaging succeed. The current artifact is
`frontend/src-tauri/target/release/bundle/appimage/Fallout Shelter_3.0.1_amd64.AppImage`
(112.08 MiB) in the build worktree. The version comes from the existing frontend
manifest, not a new release/version bump. Build output and downloaded native
libraries stay in ignored build/cache directories.

The AppImage launches directly on Bazzite outside Distrobox, maps NVIDIA EGL
without the software rasterizer, and registers its KDE tray. The maintainer
confirmed the window renders correctly with the supplied app icon. Both tray menu
actions were exercised. Window state was written and the app relaunched through
the installed desktop entry. Generated and installed desktop entries pass
`desktop-file-validate`.

A per-user test installation was created:

- AppImage: `~/.local/share/fallout-desktop/Fallout-Shelter.AppImage`
- Launcher: `~/.local/share/applications/tech.evillab.fallout.desktop`
- Icon: `~/.local/share/icons/hicolor/256x256/apps/fallout-desktop.png`

Start it from the application menu, or from a host terminal:

```bash
gtk-launch tech.evillab.fallout
# Alternatively, run the installed AppImage directly:
"$HOME/.local/share/fallout-desktop/Fallout-Shelter.AppImage"
```

For another machine, make the built AppImage executable and run it directly:

```bash
chmod +x 'Fallout Shelter_3.0.1_amd64.AppImage'
./'Fallout Shelter_3.0.1_amd64.AppImage'
```

To remove this test installation, remove exactly the three paths listed above.
The host installation uses the host's normal app data/config directories; the
Distrobox development session uses its isolated home, so it has a separate login
and window state.

Stopped at the production connectivity gate: a fresh preflight from
`tauri://localhost` still returns `400 Disallowed CORS origin`. Deploy the desktop
origins in the API CORS configuration before checking production login, packaged
gameplay notifications (including the icon), and gameplay external-link behavior.
The external-link helper has unit coverage; packaged UI verification remains pending.
No production deployment, commit, push, PR, or release publication was performed.

## Desktop build CI

[Desktop CI](../../.github/workflows/desktop-ci.yml) builds Linux x86_64 `.deb`
and AppImage packages on Ubuntu 24.04. It runs for frontend changes on pull
requests and pushes to `master`, and supports manual runs and `workflow_call`.
Windows/macOS builds and release publishing remain later work.

The workflow installs the Linux prerequisites, pnpm 11.9.0, Node 26 (matching
frontend CI), and Rust 1.99.1 (matching the tested native toolchain). It uses
the frozen pnpm lockfile and Cargo `--locked`, checks Rust formatting, and runs
the existing desktop build script with an explicit production API URL. Cargo
dependencies are cached; only `master` runs save the Rust cache. Linuxdeploy
extracts its AppImages instead of requiring a FUSE mount on the runner.

After package and desktop-entry validation, the workflow uploads both packages
and `SHA256SUMS` as `fallout-desktop-linux-x86_64-<commit SHA>`. Open the workflow
run's **Artifacts** section to download them; retention is 14 days. Extract the
artifact, verify it with `sha256sum -c SHA256SUMS`, and make the AppImage
executable with `chmod +x appimage/*.AppImage` before launching it. On a compatible
Debian/Ubuntu machine, install the Debian package with `sudo apt install ./deb/*.deb`.

These are unsigned CI test artifacts. The workflow has read-only repository
permissions, uses no deployment/signing secrets, and neither creates GitHub
releases nor changes versions. Existing frontend CI owns frontend lint,
typechecking, and unit tests; desktop CI adds native compilation and packaging.
Production API CORS deployment and installed-app visual checks remain separate
from the package build.

Local validation: `actionlint` accepts the workflow, and the exact locked package
build plus package/checksum validation commands are exercised in the Ubuntu 24.04
Distrobox. A GitHub-hosted run still requires committing and pushing the workflow;
neither was performed as part of this work.
