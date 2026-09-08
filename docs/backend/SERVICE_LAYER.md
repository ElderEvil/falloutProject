# Service Layer Contract

The foundation contract for the P0 backend service-layer rewrite. Every domain batch (chat/AI,
vault/game-loop, incidents/combat, dweller/social, quest, infrastructure) rewrites toward these rules;
new code must follow them from the start.

## Layer responsibilities

| Layer                          | Owns                                                                        | Never does                                                                           |
| ------------------------------ | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Endpoint (`api/v1/endpoints/`) | Parse params, call one service, propagate domain errors to the API boundary | Business logic, session/transaction management, CRUD calls for state changes         |
| Service (`services/`)          | Domain orchestration, transaction boundaries, raising domain exceptions     | `HTTPException`, transport formatting (headers/Responses), direct transport concerns |
| CRUD (`crud/`)                 | Persistence queries and row mutations                                       | Committing, business rules, raising transport exceptions                             |

## Transaction ownership

- A **service public entry point owns the commit** for its operation on HTTP paths. One operation, one
  transaction boundary — services may commit mid-operation only when the operation is explicitly
  multi-stage (e.g. profile after user creation).
- **Target state: CRUD never commits** and never rolls back; it only executes queries and flushes.
  Legacy exceptions include `CRUDBase` and `CRUDWastelandLocation.get_or_create` / `link_dweller`
  (default `commit=True`). Bio map registration passes `commit=False` and isolates each attempt with a savepoint.
- **Endpoints never commit** and never touch the session lifecycle.
- Background actors (Dramatiq ticks) open their own session via `task_session()` from
  `app.db.session`; that context is the transaction boundary for the tick step it wraps.

## Typed inputs and outputs

- Services accept typed parameters (`db_session: AsyncSession`, Pydantic schemas, UUIDs) and return
  domain objects: SQLModel rows or Pydantic schemas.
- No `dict` payloads as service results, no `Response`/`JSONResponse` returns, no stream/transport
  types in service signatures. Streaming services yield typed events, not HTTP primitives.

## Exceptions

- Services raise **`DomainError` subclasses** from `app/utils/exceptions.py` only. These classes
  are transport-free: they carry `status_code`/`detail`/`headers` as plain data but do not inherit
  `fastapi.HTTPException`.
- The single transport mapping point is `app.add_exception_handler(DomainError,
domain_exception_handler)` in `main.py`. Endpoints do not need per-exception try/except mapping
  anymore; existing endpoint-level mappings are removed as each domain batch touches them.
- Never catch a `DomainError` and re-raise it as `HTTPException`.
- Background code that must translate an error into an event/message (e.g. stream `error` events)
  serializes `str(e.detail)` — it does not build HTTP responses.

### Allowed `try/except` boundaries (the only ones)

1. **Streaming boundaries** — a generator that must convert one failure into an error event and
   continue the protocol (e.g. `ChatService.stream_response`).
2. **Background loop survival** — a tick/worker loop that must log and continue when one iteration
   fails.
3. **Best-effort side effects** — notifications, SSE pushes, cache writes whose failure must not fail
   the operation.

Rules for all three: log with `logger.exception(...)`, never swallow silently, at most one boundary
per operation, never nested (extract the inner block into a helper).

## Enforcement

`app/tests/test_architecture/test_service_layer_guard.py` fails the suite when any module under
`app/services/` or `app/crud/` imports or references `HTTPException`, or when
`app/utils/exceptions.py` imports fastapi. Keep it green; it is the mechanical check that batches
stay compliant.

## Known deferrals

- Chat quota validation is shared by text, streaming, and audio through `QuotaCheckResult.ensure_allowed()`.
  Rejections carry remaining/warning metadata; `main.domain_exception_handler` formats quota headers.
- `dweller_ai.py` now demonstrates the target pattern: provider/storage/audio failures raise
  `AIProviderException`/`AIStorageException`/`AIAudioException` instead of `HTTPException`.

- Chat text, streaming, and voice entry points own the conversation commit. Happiness, LLM usage creation,
  message creation, and place unlocking only flush. Recoverable agent/discovery work uses savepoints; failures
  unwind their own writes without rolling back the caller's quota lock or messages.
- `QuotaService.record_usage` stages usage in its caller's transaction; its Redis invalidation remains best-effort.
  Prompt activation commits in `create_prompt_version`; failed activation rolls back its savepoint, while failed
  prompt/profile reads retain shipped fallbacks. These queries support raw SQLAlchemy async sessions.
- Non-chat dweller AI operations still have multiple stages. Bio map writes and usage commit in the service;
  failed registration rolls back only its attempt, then sends a failure notification after usage commits.
  Legacy CRUD commits elsewhere remain deferred to their domain batches.
