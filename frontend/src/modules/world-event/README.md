# world-event

Server-wide co-op event (relay): global progress, this vault's contribution, and a one-time reward claim.
Transport: 10s polling of `GET /api/v1/vaults/:id/world-event` via `usePolling`; claim posts to `/claim`.
The view is unreachable and the Relay nav item hidden unless the backend `world_events` flag is on (default off).
