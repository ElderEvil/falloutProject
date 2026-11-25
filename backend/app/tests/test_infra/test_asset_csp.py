"""Guards that every Content-Security-Policy allows the audio the app can be fed.

Broadcast audio (Vault Radio News) is served straight from RustFS, not from the
API origin. That means two static policies — the SPA's nginx header and the
Tauri desktop policies — decide whether the player can load it at all. Both have
already shipped without the host the backend actually emits; the symptom is the
widget's "Unable to play audio" toast while the MP3 itself serves fine.

The policies are text, so the hosts are derived from their real sources: the
documented environment in `backend/.env.example`, the adapter's fallback
hostname, and the production public URL kept in the deployed secret.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import DEFAULT_RUSTFS_HOSTNAME

REPO_ROOT = Path(__file__).resolve().parents[4]
NGINX_CONF = REPO_ROOT / "frontend" / "nginx.conf"
TAURI_CONF = REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
ENV_EXAMPLE = REPO_ROOT / "backend" / ".env.example"

# The public RustFS URL the production cluster runs with, from the `rustfs-*`
# secret in `deployment/k3s`. It is not in the repo, so it is pinned here.
PRODUCTION_RUSTFS_PUBLIC_HOST = "s3-api.evillab.tech"

MEDIA_SRC_PATTERN = re.compile(r"media-src\s+([^;]+);")


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _host_from_url(value: str) -> str:
    without_scheme = value.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0].split(":", 1)[0]


def _policy_sources(policy: str) -> list[str]:
    return [token.strip("'") for token in policy.split() if token.strip("'")]


def _policy_allows(policy: str, host: str) -> bool:
    """True when a media-src value would let the browser load https://<host>."""
    for source in _policy_sources(policy):
        if source in {"*", "https:", "http:", "'self'"}:
            return True
        if source.startswith(("blob:", "data:", "http://")):
            continue
        if source.startswith("https://*."):
            domain = source[len("https://*.") :]
            if host.endswith(f".{domain}") and host != domain:
                return True
        if source.rstrip("/") in {f"https://{host}", f"https://{host}:443"}:
            return True
    return False


def _emitted_audio_hosts() -> dict[str, str]:
    """Every host a broadcast `audio_url` can be built on, with its source."""
    env = _env_example()
    hosts = {
        "production public URL": PRODUCTION_RUSTFS_PUBLIC_HOST,
        "adapter fallback hostname": DEFAULT_RUSTFS_HOSTNAME,
    }
    if public_url := env.get("RUSTFS_PUBLIC_URL"):
        hosts["backend/.env.example RUSTFS_PUBLIC_URL"] = _host_from_url(public_url)
    if hostname := env.get("RUSTFS_HOSTNAME"):
        # With no RUSTFS_PUBLIC_URL the public base URL falls back to this endpoint.
        hosts["backend/.env.example RUSTFS_HOSTNAME"] = hostname
    return hosts


def _nginx_media_policies() -> list[str]:
    policies = MEDIA_SRC_PATTERN.findall(NGINX_CONF.read_text(encoding="utf-8"))
    assert policies, "nginx.conf declares no media-src directive"
    return policies


def _tauri_media_policies() -> dict[str, str]:
    security = json.loads(TAURI_CONF.read_text(encoding="utf-8"))["app"]["security"]
    return {name: security[name]["media-src"] for name in ("csp", "devCsp") if name in security}


def test_web_media_policy_allows_every_host_a_broadcast_can_come_from() -> None:
    policies = _nginx_media_policies()
    hosts = _emitted_audio_hosts()

    for index, policy in enumerate(policies, start=1):
        for source, host in hosts.items():
            assert _policy_allows(policy, host), (
                f"nginx.conf media-src #{index} refuses {host} ({source}); Vault Radio News audio would fail to load"
            )


def test_desktop_media_policies_allow_every_host_a_broadcast_can_come_from() -> None:
    policies = _tauri_media_policies()
    hosts = _emitted_audio_hosts()

    assert policies, "tauri.conf.json declares no CSP"

    for name, policy in policies.items():
        for source, host in hosts.items():
            assert _policy_allows(policy, host), (
                f"tauri.conf.json {name} media-src refuses {host} ({source}); "
                "the desktop player would show 'Unable to play audio'"
            )


def test_every_nginx_server_block_carries_the_same_media_policy() -> None:
    # A policy fixed in one location block but not the others is the exact shape
    # of the bug: three blocks, one stale list.
    policies = _nginx_media_policies()

    assert len(set(policies)) == 1, f"server blocks disagree on media-src: {policies}"
