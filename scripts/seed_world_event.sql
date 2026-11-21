-- Staged seed for the first server-wide co-op event. Nothing schedules events today, so an
-- operator inserts the row by hand. Run statement by statement; nothing here is executed by CI.
--
--   kubectl -n fallout exec -i deploy/postgres -- psql -U <POSTGRES_USER> -d <POSTGRES_DB> \
--       -v ON_ERROR_STOP=1 < scripts/seed_world_event.sql
--
-- Editable values (all other columns are derived or fixed below):
--
--   kind            BLACKOUT_WATCH
--   title           Blackout Watch
--   description     one line, civil-defence tone
--   target_amount   400
--   personal_min    20
--   reward          [{caps 2000}, {lunchbox 1}]  -- keys consumed by reward_service.grant
--   starts_at       now() + 1 hour
--   ends_at         starts_at + 7 days
--   status          SCHEDULED
--   id              literal (worldevent.id has no server default; the ORM generates it)

-- 1) Clear a stuck ACTIVE event. This ends whatever is ACTIVE, including a genuinely running
--    event, so only run it when an ACTIVE row blocks the seed below.
UPDATE worldevent
SET status = 'EXPIRED', updated_at = now()
WHERE status = 'ACTIVE';

-- 2) Insert the first event. Re-runnable: no-op while a SCHEDULED or ACTIVE event exists.
WITH seed AS (
    SELECT
        '019a5e2c-7b4d-7c31-9f2a-6d1e8c4b5a70'::uuid AS id,
        'BLACKOUT_WATCH'::varchar(50) AS kind,
        'Blackout Watch'::varchar(120) AS title,
        'The lights went out across the wasteland. Man the civil-defence stations and survive the dark.'::varchar(500) AS description,
        400 AS target_amount,
        20 AS personal_min,
        '[{"reward_type": "caps", "amount": 2000}, {"reward_type": "lunchbox", "amount": 1}]'::jsonb AS reward,
        now() + interval '1 hour' AS starts_at
)
INSERT INTO worldevent (
    id, kind, title, description, target_amount, progress_amount, personal_min,
    reward, starts_at, ends_at, status, created_at, updated_at
)
SELECT
    seed.id, seed.kind, seed.title, seed.description, seed.target_amount, 0, seed.personal_min,
    seed.reward, seed.starts_at, seed.starts_at + interval '7 days', 'SCHEDULED', now(), now()
FROM seed
WHERE NOT EXISTS (SELECT 1 FROM worldevent WHERE status IN ('SCHEDULED', 'ACTIVE'));

-- 3) Cleanup, destructive: delete only the seeded row, and only with explicit approval.
-- DELETE FROM worldevent WHERE id = '019a5e2c-7b4d-7c31-9f2a-6d1e8c4b5a70';
