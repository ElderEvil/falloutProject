# Linux desktop

The Tauri v2 shell shares the Vue frontend and supports Linux x86_64 `.deb` and
AppImage packages. Track remaining release work in [issue #1392](https://github.com/ElderEvil/falloutProject/issues/1392)
and the [implementation plan](../plans/2026-11-11-tauri-desktop.md).

## Development and packaging

On Bazzite, use the Ubuntu 24.04 Distrobox `fallout-tauri-nvidia`, created with
NVIDIA integration, and a separate build worktree. Its isolated home is
`~/.local/share/fallout-tauri/home`; host installations have separate login/config
state. The original `fallout-tauri` box is retained as a stopped fallback.

```bash
distrobox enter fallout-tauri-nvidia
cd /var/home/elder/Projects/falloutProject-tauri/frontend
pnpm install --frozen-lockfile
pnpm run desktop:dev
# Native debug binary, without installers:
pnpm run desktop:build --debug --no-bundle
# Release packages; explicitly override any ignored local API setting:
VITE_API_BASE_URL=https://fallout-api.evillab.tech pnpm run desktop:build --ci --bundles deb,appimage -- --locked
```

Use the [Tauri Linux prerequisites](https://v2.tauri.app/start/prerequisites/).
The tested native toolchain is Rust 1.99.1 and pnpm 11.9.0; local Node is 22.22.3,
while CI uses Node 26. Packages appear under `frontend/src-tauri/target/release/bundle/`.
Semantic Release owns the version in `frontend/package.json`; the Cargo crate's
`0.0.0` is internal metadata. Keep both dependency lockfiles committed.

Desktop development uses strict port 5173, ignores native build files, and skips
automatic OpenAPI generation. Run `pnpm run types:generate` after API schema changes.
`.env.desktop` selects production; use an ignored `.env.desktop.local` or
`VITE_API_BASE_URL=http://localhost:8000 pnpm run desktop:dev` for a local backend.
Production CSP permits the production API; development CSP also permits local API
and HMR connections. Custom API/media hosts require corresponding CSP changes.

Runtime warning fixes installed in the NVIDIA box: `kde-config-gtk-style`,
`appmenu-gtk3-module`, `gstreamer1.0-plugins-bad`, and `gstreamer1.0-tools`.
Both `fakevideosink` and `webvttenc` resolve. NVIDIA EGL replaced llvmpipe in the
app and WebKit renderer; live CPU/memory samples were not a controlled benchmark.

## Native behavior

Closing the window hides it after successful tray creation. **Show Fallout
Shelter** restores/focuses it; **Quit** exits. If tray creation or hiding fails,
closing quits normally. Size, position where supported, and maximized state are
saved; hidden/minimized state is excluded so the next launch opens visibly.

The bell owns notification deduplication and native delivery. Only its SSE stream
stays active while the desktop is hidden; other subscriptions/gameplay polling
retain visibility-based pausing. Native alerts recheck session, token, selected
vault (including its saved selection before hydration), and visibility after
asynchronous permission/resource lookup. Denied permission preserves in-app alerts.
Alerts require the app process to remain running, including hidden to the tray.

The API starts the existing Redis broadcast listener even without a WebSocket.
Workers use per-call publisher clients to avoid sharing pools between event loops.
Sender-instance filtering prevents echoes; reconnect/resubscription closes only
notification SSE streams so clients reload the persisted recent inbox. Pub/Sub is
best-effort, not durable. Commit/deferred-delivery ownership is unchanged; see
[SERVICE_LAYER.md](../backend/SERVICE_LAYER.md).

HTTP(S) anchors and the changelog link use the system browser. Provider sign-in on
login/registration and provider linking in settings are hidden on desktop until
an OAuth return flow exists. Browser OAuth and existing connection management
remain available. Capabilities permit only the main window's notification and
scoped HTTP(S) opener operations, with no filesystem opener permission.

The supplied 1024px vault/lightning source is `frontend/src-tauri/app-icon.png`.
Tauri's icon CLI generates platform sizes. The source and embedded PNGs in
`icons/icon.icns` were palette-compressed with pngquant to fit the 500 KB guard;
regeneration may require recompression. Notification delivery resolves a bundled
128px PNG explicitly rather than relying on KDE's executable-name icon lookup.

## CI and installation

[Desktop CI](../../.github/workflows/desktop-ci.yml) builds on Ubuntu 24.04 for
frontend PRs, `master` pushes, manual runs, and reusable workflow calls. It pins
Rust/pnpm, uses frozen/locked dependencies, checks Rust formatting, validates Debian
metadata/desktop entries, and uploads packages plus `SHA256SUMS` for 14 days.
Only `master` saves Rust caches; linuxdeploy uses extraction instead of FUSE.
Existing frontend CI owns lint, typechecking, and unit tests. Desktop CI has
read-only permissions and does not publish releases, change versions, or use
signing/deployment secrets. Artifacts are unsigned test packages.

Download `fallout-desktop-linux-x86_64-<commit SHA>` from the run's **Artifacts**
section, extract it, then:

```bash
sha256sum -c SHA256SUMS
chmod +x appimage/*.AppImage
./appimage/*.AppImage
# Alternatively, on compatible Debian/Ubuntu:
sudo apt install ./deb/*.deb
```

The Bazzite test installation uses these per-user paths:

- AppImage: `~/.local/share/fallout-desktop/Fallout-Shelter.AppImage`
- Launcher: `~/.local/share/applications/tech.evillab.fallout.desktop`
- Icon: `~/.local/share/icons/hicolor/256x256/apps/fallout-desktop.png`

Start with `gtk-launch tech.evillab.fallout` or run the installed AppImage directly.
Remove those three paths to uninstall this test installation.

## Validation and rollout gates

Local validation passed frontend lint/typechecking/build, Rust formatting/checks,
locked release packaging, desktop-entry validation, and package checksums. Focused
suites passed: 78 notification/SSE/desktop frontend tests, 64 auth/profile/desktop
tests, 78 backend bridge/notification/lifecycle/architecture tests, and 25 CORS/
deployment tests. Counts overlap between suites. Packaging produced a 37 MiB Debian
package and 112 MiB AppImage. The AppImage launched directly on Bazzite with NVIDIA
EGL; window/icon, tray actions, saved state, and launcher startup were checked.
A real worker notification reached authenticated API SSE, and a hidden-window OS
alert was visually confirmed against the local backend.

Production preflights rejected desktop origins on 2026-11-12. Both backend defaults
and the k3s manifest now preserve the website origin and allow `tauri://localhost`,
`http://tauri.localhost`, and `https://tauri.localhost`; that manifest still needs
rollout. Explicit environment overrides replace defaults. HTTP CORS covers SSE,
not WebSocket handshakes.

Before release, verify packaged production password login/refresh/sign-out/expiry,
vault/media/chat/SSE/reconnect, the updated notification icon, external links,
and Debian installation. Confirm actual media hosts against CSP. Production has
not been changed as part of this PR. OAuth return handling, signed updates,
release publishing, and other platforms remain follow-up work.
