# Backend Scripts

Developer utilities for the Fallout Shelter backend. All Python scripts are
[Typer](https://typer.tiangolo.com/) CLIs with a uniform interface:

- Run from `backend/`: `uv run python scripts/<name>.py --help`
- Each script has typed options with `--help` documentation
- Scripts that touch the DB read `ASYNC_DATABASE_URI` from `backend/.env`

**Layout convention:** this directory holds *backend* (Python) scripts.
Repo-root `scripts/` holds general shell utilities such as `backup-db.sh`.
Development startup is provided through the project Zed tasks.

## Admin & Data Migration

| Script | Purpose |
|---|---|
| `create_admin.py` | Create/upgrade a superuser (admin) account for testing |
| `migrate_quest_data.py` | Migrate legacy quest requirement/reward strings into structured DB records |

## Game Data & Balancing

| Script | Purpose |
|---|---|
| `simulate_happiness_balance.py` | Monte-Carlo simulation of happiness balance |
| `simulate_incident_balance.py` | Monte-Carlo simulation of incident balance |
| `simulate_resource_economy.py` | Deterministic resource-rate scenario using the live `ResourceManager` formulas |
| `simulate_exploration_balance.py` | Monte-Carlo simulation of exploration balance |
| `BALANCE_FINDINGS.md` | Findings notes from balance tuning runs |

## Dweller Data

| Script | Purpose |
|---|---|
| `backfill_dweller_bio_places.py` | Extract origin/visited places from existing dweller bios and register them on the world map (`--vault`, `--max-dwellers`) |
| `backfill_unlock_discoveries.py` | Link DISCOVERY locations to their finding dweller and mark them unlocked (pre-fix discoveries had no dweller link) (`--vault`, `--all-active`) |
| `fill_dweller_bios_templates.py` | Fill empty dweller bios with SPECIAL-driven template backstories that reference map places |

## Infrastructure

| Script | Purpose |
|---|---|
| `fix_dweller_image_urls.py` | Convert dweller image filenames to full storage URLs |
| `set_rustfs_bucket_policies.py` | Set public read policies on whitelisted RustFS buckets |

## Standalone Tools

| Script | Purpose |
|---|---|---|
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

All other scripts use the project environment and run with `uv run python scripts/<name>.py`.
