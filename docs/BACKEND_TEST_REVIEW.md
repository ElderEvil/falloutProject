# Backend Test Usefulness and Simplification Review

Date: 2026-10-13

## Summary

The suite provides useful protection, but has accidental complexity in shared fixtures and repeated test scaffolding. Optimize setup first, consolidate proven duplicate scenarios second, and avoid broad test deletion.

The ultimate goal is simpler application and test architecture—not the smallest possible test count.

### Inventory

- 2,766 collected tests
- 2,261 test-function definitions across 236 test files
- Approximately 56,920 lines in those test files
- Service tests account for 1,334 definitions, making them the largest simplification area

The review covered API/CRUD, services, and a sample across models, schemas, utilities, agents, migrations, and architecture guards. It is not an exhaustive rating of every test. Definition counts exclude parametrization expansion; line counts include comments and blank lines.

Paths below are relative to the repository root.

### Usefulness scale

| Rating | Meaning |
|---|---|
| 5/5 | Distinct security, concurrency, migration, regression, or critical behavior protection |
| 4/5 | Meaningful behavioral contract |
| 3/5 | Useful case, but repetitive scaffolding or weak assertions |
| 2/5 | Little additional protection beyond another test |
| 1/5 | Tests supplied literals, incidental inventory, or behavior it never actually exercises |

Scores concern each test's additional protection, not the importance of its feature. Low scores identify review candidates, not automatic deletion approval.

## 1. Highest-priority speedup: reduce fixture work

### HTTP tests unnecessarily create a superuser

In `backend/app/tests/conftest.py:148`, `async_client` depends on `superuser`. Even anonymous-request tests therefore create a database user through CRUD and hash its password.

The targeted timing run showed:

- Anonymous-route cases spending approximately 0.19 seconds in setup
- Authenticated cases spending 0.36–0.73 seconds in setup

These measurements do not isolate hashing as the sole cause, but support investigating setup before deleting assertions.

**Recommendation:** decouple `async_client` from superuser creation. Make authenticated fixtures explicitly request the user they need. For non-authentication tests, consider known precomputed password hashes in fixture-created users, while retaining real hashing/login coverage in authentication tests.

Production hashing settings must remain unchanged.

### Every test initializes and flushes fakeredis

`backend/app/tests/conftest.py:55–74` installs two autouse fixtures for all tests, including pure schema and utility tests.

**Recommendation:** make Redis setup explicit or restrict its scope to tests needing it. A newly created function-scoped fake client is also flushed before and after use; investigate whether both flushes serve any purpose before removing them.

This reduces infrastructure coupling as well as runtime. Savings have not yet been measured.

### Measure before increasing parallelism

Local defaults already use two workers; coverage CI uses `-n auto`.

Adding workers multiplies application imports and worker-local initialization. Compare serial, two-worker, and automatic-worker runs after reducing fixture costs rather than assuming more workers are better.

## 2. Concrete overlap candidates

These are good first consolidation candidates, subject to the repository's deletion-validation policy.

| Value | Tests / location | Suggested change |
|---|---|---|
| 2/5 | `backend/app/tests/test_crud/test_room.py:690,735`: `test_upgrade_keeps_merged_size_and_scales_capacity` and `test_upgrade_charges_every_merged_segment` | Same room setup and upgrade operation. Combine size, capacity, output, art, and cost assertions into one scenario. |
| 2/5 | `backend/app/tests/test_crud/test_pet.py:66,161`: `test_reequip_returns_displaced_pet_to_storage` and `test_equip_does_not_delete_displaced_pet` | Combine, preserving explicit persisted existence, storage routing, and new-pet ownership assertions. |
| 2/5 | `backend/app/tests/test_crud/test_item_base.py:169` versus `backend/app/tests/test_crud/test_item_equip.py:99`: same-item equip rejection | Prefer the database-backed scenario; the mocked version adds little independent protection. |
| 1/5 | `backend/app/tests/test_api/test_route_auth_enforcement.py:100`: `test_authenticated_reads_still_work` | `backend/app/tests/test_api/test_weapon.py:36` checks the same authenticated request plus actual response contents. Preserve anonymous, foreign-vault, and privileged-write tests. |
| 2/5 | `backend/app/tests/test_services/test_radio_service.py:217,232`: return tuple versus fresh recruit | Add explicit tuple/type assertions to the deterministic fresh-recruit test; eliminate the separate shape-only operation. Unpacking alone does not establish tuple type. |
| 1/5 | `backend/app/tests/services/test_quota_service.py:139,157`: result creation and “immutability” | Reads supplied literals back. The “immutability” test only checks types, and the dataclass is not frozen. Fold necessary result-field assertions into behavioral tests. |
| 1/5 | `backend/app/tests/test_models/test_medical_storage.py:71` versus `:34,42` | Repeated default assertions can become one coherent default contract. Keep medical-field ownership checks. |
| 2/5 | `backend/app/tests/test_ai_usage_service.py:27,114` | Similar legacy schema payloads with complementary assertions. Combine into one backward-compatibility test. |

These are modest execution-count reductions, not justification for a large pruning batch. Their main value is removing repeated setup and maintenance.

## 3. Consolidations that reduce complexity, not executions

The following cases should remain independently exercised, but can share small parametrized tests:

- **Relationship endpoint errors:** repeated not-found and service-rejection scaffolding in `backend/app/tests/test_api/test_relationship.py:191–418`.
- **Training endpoint errors:** repeated complete/cancel exception mapping in `backend/app/tests/test_api/test_training.py:391–503`.
- **Resource rewards:** water and power cases in `backend/app/tests/test_services/test_reward_service_extended.py:314,336`.
- **Room merge occupants:** retained-room occupants versus absorbed-room occupants in `backend/app/tests/test_services/test_room_service.py:376,552`.

Preserve route-specific exception types and assertions. In particular:

- Marriage and other relationship operations currently inject different exception types.
- Training lookup returning `None` differs from the service raising not-found after a successful lookup.
- Preserving an occupant in the surviving room differs from moving an occupant out of the absorbed room.
- Resource overflow and invalid-resource rejection remain separate contracts.

**Parameterization reduces source duplication; it does not reduce collected cases or inherently improve runtime.**

Also consolidate quota tests under the existing `test_services/` location rather than maintaining both `tests/services/` and `tests/test_services/`. Keep configuration-disabled and administrator bypasses as distinct cases. Avoid introducing a generic test framework to achieve these consolidations.

## 4. Weak tests to strengthen before judging redundancy

| Current value | Example | Problem |
|---|---|---|
| 1/5 | `backend/app/tests/test_utils/test_seed_objectives.py:107` | “Validates schema” accepts any nonnegative count, including zero; does not prove invalid rows were rejected and valid rows retained. |
| 1/5 | `backend/app/tests/test_models/test_prompt.py:24` | “Defaults” test uses a helper that explicitly supplies those defaults. Changing model defaults would not fail it. |
| 1/5 | `backend/app/tests/test_agents/test_synth_concealment.py:37` | Claims portrait-agent routing protection but only exercises a helper. |
| 1/5 | `backend/app/tests/test_agents/test_list_all_rooms.py:116` | `len(all_tools) >= 4` would pass with four irrelevant tools. Named registration assertions are more useful. |
| 3/5 | `backend/app/tests/test_services/test_radio_service.py:403` | Reset assertions for radiation and partner start with already-reset values. Dirty those fields first. |

These findings matter more to application simplicity than raw counts: tests should describe real contracts rather than incidental implementation details.

## 5. Protections to preserve

Do not prune the following merely because they cover overlapping lines:

- PostgreSQL enum snapshots, native-column configuration, and live-database checks
- Executed migrations, idempotent backfills, and preservation of existing data
- Locks, concurrency, transaction ownership, and tick-session compatibility
- Authorization, ownership, and HTML-injection checks
- Catalog factory mapping and guards against bypassing the factory
- Agent validation against live gameplay state
- Architecture dependency ratchets and their scanner self-tests
- Boundary cases for damage, capacity, cooldowns, and resource overflow

They protect different failure modes even when their source coverage overlaps. SQLite execution does not establish PostgreSQL safety, and integration checks skipped because PostgreSQL is unavailable are not validated by a green default run.

## 6. Recommended implementation plan

### Step 1: establish current runtime and coverage baselines

From `backend/`:

```sh
uv run pytest app/tests --durations=30 \
  --cov=app --cov-context=test --cov-report=json
```

Preserve the baseline coverage data and JSON report before another run overwrites them. Inspect slow setup, call, and teardown phases separately. Record worker count and infrastructure availability so comparisons remain meaningful.

### Step 2: remove unnecessary fixture work

Start with automatic superuser creation and global Redis setup. Prove isolation and authentication behavior remain intact. Benchmark before and after.

### Step 3: consolidate small duplicate scenarios

Use the candidates in section 2, retaining their combined assertions. Work in small batches.

### Step 4: parameterize local repeated families

Use section 3. Preserve every distinct case and avoid cross-module test abstractions.

### Step 5: strengthen misleading tests

Use section 4. Fix weak inputs and assertions before relying on these tests to justify removal of another test.

### Step 6: validate every deletion batch

Follow the repository's test-pruning policy:

- Preserve at least one behaviorally distinct test for every public contract, regression, boundary/error path, migration, concurrency guarantee, security/auth check, and assertion-diverse or parametrized family.
- Run collection and the full backend suite with coverage.
- Compare the covered-line delta against the baseline.
- Audit orphaned fixtures and helpers.
- Record deleted scope, test-count change, coverage delta, protected families, and validation commands in the PR description.

Coverage shadowing identifies candidates; it does not prove deletion is safe. Tests without coverage contexts are not dead code.

## 7. Connection to overall application complexity

This review supports simplifying test representation and infrastructure first. It does not yet justify removing production behavior.

Long patch blocks and overlapping suites are useful signals for a later production review: look for competing implementations, unnecessary forwarding layers, or unclear ownership of business rules.

Keep the established endpoint → service → CRUD boundaries. Collapsing those layers would trade fewer files for greater coupling. Preserve architecture guards because they help prevent future complexity.

## 8. Validation and limitations

Executed during the review:

```sh
UV_CACHE_DIR=/tmp/fallout-review-uv uv run --offline --no-sync \
  pytest app/tests --collect-only -q -n 0
```

Result: **2,766 tests collected**.

```sh
UV_CACHE_DIR=/tmp/fallout-review-uv uv run --offline --no-sync pytest \
  app/tests/services/test_quota_service.py \
  app/tests/test_models/test_medical_storage.py \
  app/tests/test_api/test_weapon.py \
  app/tests/test_api/test_route_auth_enforcement.py \
  -n 0 --durations=15 --tb=short -q
```

Result: **53 passed in 11.07 seconds**, with one SQLAlchemy table-drop dependency warning involving `dweller` and `room`.

Existing coverage data:

- Report timestamp: 2026-09-07
- Line coverage: 84.24%
- Branch coverage: disabled
- Per-test contexts: absent; the coverage database contains only the empty context

That historical report cannot substantiate a current overlap ranking. No full-suite benchmark, coverage-shadow analysis, or deletion experiment was run. The review made no code or test changes, and existing user changes were left untouched.

**Best next step: optimize the shared fixtures before pruning tests.** This offers a broader potential speedup while preserving behavioral coverage.
