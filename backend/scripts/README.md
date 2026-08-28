# Backend Scripts

Developer utilities for the Fallout Shelter backend.

**Layout convention:** this directory holds *backend* (Python) scripts.
Repo-root `scripts/` holds general shell utilities such as `backup-db.sh`.
Interactive management commands (superuser creation, backfills, smoke tests)
have moved into the `fo-cli` entry point defined in `pyproject.toml`.
Development startup is provided through the project Zed tasks.

## `fo-cli` management commands

Run from `backend/`:

```bash
uv run fo-cli --help
```

| Command | Purpose |
|---|---|
| `fo-cli createsuperuser` | Create/upgrade a superuser (admin) account |
| `fo-cli seed` | Re-seed quests and objectives from JSON files |
| `fo-cli family-scenario` | Dev/QA: build family/breeding test scenarios |
| `fo-cli pregen-dwellers` | Dev/QA: seed dwellers with deterministic bios + map markers |
| `fo-cli dweller-bios` | Dev/QA: fill missing bios for existing dwellers |
| `fo-cli backfill backfill-bio-places` | Extract origin/visited places from bios and register them on the world map (`--vault`, `--all-active`, `--max-dwellers`) |
| `fo-cli backfill backfill-unlock-discoveries` | Link DISCOVERY locations to their finding dweller and mark them unlocked (`--vault`, `--all-active`) |
| `fo-cli ops fix-dweller-image-urls` | Convert dweller image filenames to full storage URLs |
| `fo-cli ops set-rustfs-policies` | Set public read policies on whitelisted RustFS buckets |
| `fo-cli ops check-ai` | HTTP smoke test against a live API server (`--api-url`, `--skip-chat`, `--expect`) |

## Game Data & Balancing

| Script | Purpose |
|---|---|
| `simulate_happiness_balance.py` | Monte-Carlo simulation of happiness balance |
| `simulate_incident_balance.py` | Monte-Carlo simulation of incident balance |
| `simulate_resource_economy.py` | Deterministic resource-rate scenario using the live `ResourceManager` formulas |
| `simulate_exploration_balance.py` | Monte-Carlo simulation of exploration balance |

Balance findings are documented in [`docs/features/BALANCE_FINDINGS.md`](../../docs/features/BALANCE_FINDINGS.md).

## Standalone Tools

| Script | Purpose |
|---|---|
| `download_wiki_images.py` | Download Fallout Shelter images from The Vault wiki |

`download_wiki_images.py` is a self-contained [PEP 723](https://peps.python.org/pep-0723/)
script with inline dependencies. It uses the Fandom MediaWiki API and supports
rooms, weapons, apparel icons, and legendary dweller cards. By default, images
are saved under `app/static/` and legendary dweller metadata is saved to
`app/data/vault/legendary_dwellers.json`:

```bash
cd backend
uv run scripts/download_wiki_images.py rooms
uv run scripts/download_wiki_images.py weapons
uv run scripts/download_wiki_images.py apparel
uv run scripts/download_wiki_images.py legendary-dwellers

# Or download everything at once
uv run scripts/download_wiki_images.py all
```

All other Python scripts use the project environment and run with `uv run python scripts/<name>.py`.
