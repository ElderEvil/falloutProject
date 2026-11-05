# Vault Radio Hour — Implementation Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Procedural "radio news broadcast" for each vault — a 1950s-style DJ clip rendered from the vault's live DB state, playable in-game.

**Architecture:** New backend `broadcast_service` renders a deterministic DJ script from vault state (population, caps, resources, happiness, recent notifications), synthesizes it via a TTS provider (OpenRouter HeyGen first, ElevenLabs fallback), stores the clip in S3, and serves it through a REST endpoint. The frontend gets a radio HUD widget that plays the daily broadcast. Vintage fx chain (band-limit, crackle, slow-down) is applied server-side with ffmpeg when available, else the raw voice ships.

**Tech Stack:** FastAPI + SQLModel, dramatiq (not needed for MVP), httpx (TTS), boto3/S3 (RustFS, reuse existing storage utils), ffmpeg (post-processing, optional at runtime), Vue 3 + TS module.

## Playback design (where & when)

1. **Daily news on first vault load of the day** — endpoint returns today's broadcast, cached per vault per UTC day. Frontend shows a "📻 New broadcast" badge (browser autoplay policies forbid auto-sound); one tap plays it.
2. **Radio room (diegetic)** — clicking an existing Radio Studio room plays the broadcast. Phase 2.
3. **HUD radio button** — manual tune-in, replays cached clips any time (free).
4. **Breaking news (Phase 2)** — HIGH-priority notifications debounced 10 min, max 3 renders/vault/day.
5. **Saturday weekly recap to Discord (Phase 3)** — fits the existing Saturday changelog flusher.

MVP implements 1 + 3.

## API contract (fixed — frontend may build against it before backend lands)

- `GET /api/v1/vaults/{vault_id}/radio-news`
  - Returns today's broadcast, generating it on first call of the UTC day.
  - Response: `{"id": uuid, "title": str, "script": str, "audio_url": str, "trigger": "daily", "created_at": iso}`
  - `audio_url` is a presigned/parseable S3 URL. If TTS is down: `{"id": null, "script": str, "audio_url": null, ...}` with the script so the UI can still show text.
- `POST /api/v1/vaults/{vault_id}/radio-news/regenerate` — manual re-render, rate-limited to 3/UTC day/vault (429 with `detail` beyond).

Auth: standard vault-access dependency, same as other vault endpoints.

## Tasks

### Task 1: Model + migration
- Create `Broadcast` model in `backend/app/models/broadcast.py`:
  `id (uuid pk)`, `vault_id (fk)`, `title (str)`, `script (text)`, `audio_key (str | None)`, `trigger (str: daily|manual)`, `created_at`, `updated_at`.
- Alembic migration `backend/app/alembic/versions/` (follow the latest migration's style; index on `(vault_id, created_at)`).

### Task 2: OpenRouter TTS provider
- Create `backend/app/services/openrouter_tts_service.py` mirroring `elevenlabs_service.py`'s shape:
  - `is_enabled` ← `settings.OPENROUTER_API_KEY` (add to `app/core/config.py` if absent).
  - `async generate_speech(text) -> bytes`: POST `https://openrouter.ai/api/v1/audio/speech`, JSON `{"model": "heygen/heygen-voice-1-turbo:free", "input": text, "voice": "weston", "response_format": "pcm"}`. Response is raw s16le mono 44.1 kHz PCM — wrap it into a WAV header in Python (stdlib `wave`/`io`, no numpy) and return WAV bytes.
  - Errors → new `TTSProviderException` in `app/utils/exceptions.py`, same patterns as `ElevenLabsProviderException` (401/429/other, transport errors).
- Provider selection: `broadcast_service` uses OpenRouter when enabled, else falls back to `ElevenLabsTtsService`, else returns script-only.

### Task 3: Script renderer
- Create `backend/app/services/broadcast_script_service.py` — pure function(s), no I/O:
  `build_daily_script(vault, dweller_stats, recent_notifications) -> tuple[title, script]`.
- Facts to weave in: population + gender split, bottle_caps, power/food/water vs max, happiness %, up to 3 notable recent notifications (level-ups batched to one line: "N residents reached level N tonight", name up to 2 dwellers). 1950s radio announcer diction, 120–180 words, sign-off at the end. No LLM in MVP.

### Task 4: Broadcast service + endpoint
- Create `backend/app/services/broadcast_service.py`:
  - `get_or_create_daily(db, vault)`: find today's broadcast (UTC date, trigger='daily'); if absent, build script, call TTS, post-process, upload to S3 (reuse whatever narration/asset storage util exists — search for how narration clips are uploaded), persist row, return.
  - `regenerate(db, vault)`: same but trigger='manual'; enforce 3/day cap via count query.
  - `_post_process(wav_bytes) -> bytes`: if `shutil.which("ffmpeg")`, pipe through
    `ffmpeg -f s16le -ar 44100 -ac 1 -i - -af "asetrate=44100*0.92,aresample=44100,highpass=f=300,lowpass=f=3200,tremolo=f=9:d=0.04,loudnorm=I=-16:TP=-1.5" -b:a 128k -f mp3 -`
    (slower tape feel + AM band-limit). Else return WAV unchanged. Log which path was taken.
- Endpoint file `backend/app/api/v1/endpoints/radio_news.py`, router registered in `api.py`.
- TTS failures: log + return script-only response (never 500 the endpoint).

### Task 5: Tests
- `backend/app/tests/` — follow existing service test conventions (search `test_radio` or `test_notification` for the fixture style).
- Cover: script renderer facts (gender split, resource ratios, notification batching, level-up line), provider WAV wrapping (feed fake PCM, assert RIFF header + size), daily cache (second GET same day = no second TTS call), regenerate cap, TTS-failure degradation path.
- Mock all HTTP (httpx MockTransport) and S3. No network in CI.

### Task 6: Frontend radio widget
- New module `frontend/src/modules/radio-news/`:
  - `api/radioNews.ts` — typed client for the two endpoints (mirror `modules/radio/api/radio.ts` style).
  - `components/RadioNewsWidget.vue` — HUD button with 📻 icon; badge when `created_at` is today and unplayed; click plays `audio_url` via a plain `Audio` element (see `useChatAudio` for the existing pattern); shows script text as a caption while playing; hidden/disabled when audio_url is null but script exists (show text-only broadcast).
- Mount the widget in the vault HUD (find where other HUD buttons/quick actions render; follow `modules/radio`'s integration as reference). Loading + error states required; no audio autoplay.

### Task 7: Lint, full test suites, PR
- Backend: run the repo's standard pytest suite + ruff/pre-commit as CI does.
- Frontend: vue-tsc/typecheck + unit tests.
- Push branch `feat/vault-radio-hour`, open PR referencing the tracking issue.

## Repo rules
- Branch from `origin/master` (NOT the current dirty `fix/tick-envelope-regression` checkout; do not touch `frontend/tests/unit/stores/vault.test.ts` — pre-existing unrelated modification).
- Never create git tags (semantic-release owns them).
- One commit per task, conventional commits.
