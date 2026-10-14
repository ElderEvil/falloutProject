# Spotlight onboarding

> Status: **planning and sanity-check specification**. The spotlight shell shipped in #995
> (v2.203.0). The first-session sequence is being rebuilt. This document specifies the full
> player journey and implementation gates; it does not certify that the proposed flow works yet.
> Working-tree departure/catalog changes may exist, but are not evidence of a complete rollout.

## Goal and scope

From vault creation onward, show one useful action the player can take now. Teach enough to run
an independent vault, then offer contextual lessons as systems unlock. A player should be able
to leave, return, skip the tour, or play out of order without losing earned rewards or getting stuck.

The short orientation and the long-running starter objective arc are different things. Finishing
orientation must not require 14/18 dwellers, an expedition return, a trained stat, or a rare drop.
Later starter chapters remain available through the guide and the Overseer Briefing. Their waits
must never keep the screen dimmed.

This is a documentation/planning task. Feature implementation, migrations, balance changes,
and release are subsequent work. The game-domain rules in
[GAME_MECHANICS.md](../backend/GAME_MECHANICS.md) remain binding. Changing the starter arc contract
or its visibility after the Office requires an explicit, coordinated update to those rules.

## Acceptance criteria

- Spotlight an available action; show waiting, locked, unavailable, or unaffordable work without dim.
- Preconditions cover eligibility, room space, placement, caps, supplies, and prerequisites.
- Teach look → understand staffing → expand capacity → dispatch → grow → use unlocked systems.
- Aim for 3–6 minutes of active orientation; treat this as a playtest target, not a timer requirement.
- A step should normally take under two minutes of player interaction. Never pad the tour to delay
  its first background operation; expedition travel starts when the player dispatches.
- The player explicitly claims server rewards. Claim success advances server steps; a tap never
  pays rewards or marks a server objective claimed.
- One prominent guide action at a time. Incidents, resource recovery, and player-opened dialogs
  take visual priority. Notifications/toasts and successful-claim surfacing remain intact.
- No seed changes merely to manufacture idle adults. Reward-based arrivals remain preferred.
- Already-built rooms, existing expeditions, skipped steps, and migrated progress have deliberate
  completion rules. Neither local-storage reset nor repeated clicks can replay rewards.

## Evidence and corrections to Phase 0

The throwaway probe used `vault_service.initiate_vault(is_boosted=False)` and was deleted:

- Caps **1000**, `population_max` **8**, power/food/water **75 / 150** each.
- Vault Door (size 6), four Elevators (size 1), Living room (size 3, capacity 8),
  Storage room (size 3, capacity 30), Power Generator/Diner/Water Treatment (size 3, output 28),
  and Radio studio (size 3).
- Ten dwellers, all placed: three Power workers including a teen and elder, two Diner workers,
  two Water workers, one Radio worker, and two resting adults in the Living room.
- The observed resting adults were Heywood and Elizabeth. Names, rarity and SPECIAL are not
  invariant: standard Living-room adults are randomly created without a SPECIAL boost.
- The probe's SQLite catalog lacked objective templates. Production seeds objectives from JSON;
  tests for this flow must load that catalog too.

Code inspection changes the interpretation of that snapshot:

| Finding | Consequence for the plan |
|---|---|
| Shared departure eligibility excludes youth, dead/deleted and exploring/questing dwellers; it does not require an idle, unassigned adult | No idle adult does **not** prove departure is impossible. Check the actual picker and API. Prefer the reward arrival to protect production, rather than because departure strictly requires it. |
| Standard production rooms have two adult workers; auto-assignment uses two adult slots per size-3 segment, excluding apprentices | Movable Living-room adults do not guarantee a valid auto-assignment. Their best SPECIAL may have no matching room or no free slot. |
| Manual `move_to_room` and automatic assignment have different checks | Do not exploit manual overstaffing to make a lesson work. Any capacity-policy discrepancy needs a separate failing test and domain decision. |
| `current_state_progress` credits existing matching workers and rooms | An assignment lesson may already be ready; the seeded Living room may satisfy a target of one. A claimed arrival can then fail because population is already 10/8. |
| Objective settlement parses one reward string | `50 caps` plus `dweller:Wanderer` is not supported as a bundle. Prefer an arrival-only reward for the capacity lesson. |
| `template_key` exists on stored templates, but is absent from `ObjectiveRead` and its CRUD projection | Frontend lookup by key needs an API/model update and regenerated types. Do not identify objectives by translated challenge text. |
| Radio recruitment rolls a probability and can switch a full vault to happiness mode | Never promise a fixed six-hour arrival or assume recruitment remains enabled after expanding capacity. |
| The resource simulator builds only three production rooms with uniform staffing | It is a useful formula check, not proof that the full seed plus tutorial actions is stable. |

Sources: `backend/app/services/vault/seeding.py`, `dweller_service.py`, `exploration_service.py`,
`rewards/settlement.py`, `rewards/items.py`, `radio_service.py`,
`progression/objectives/guidance.py`, `backend/app/crud/objective.py`, and
`backend/app/cli/simulate_resources.py`.

## The player journey

### A. First-session orientation

Keep the base sequence, but make its uncertain assignment requirement explicit. The recommended
initial version teaches the existing correct staffing rather than demanding an unsafe transfer.
A genuine reassignment objective is acceptable only after the feasibility gate below passes.

| Step | Player experience | Kind / anchor | Completion and reward | Preconditions / fallback |
|---|---|---|---|---|
| 0 | Welcome: “Keep the vault supplied, make room for arrivals, and send an explorer.” Start / Skip | Client card; no anchor | Start dismisses welcome; no reward | New standard vault with starter links. Existing/boosted vaults get optional Help access. |
| 1 | Explain power stock, capacity and net trend; food/water follow the same pattern | Tap `resource-power` | Deliberate target activation or card Continue; no reward | Visible bar. On mobile navigate to the vault screen before highlighting. |
| 2 | Open the Power Generator; show Strength, current workers and production | Tap `room-power` | Room opened and lesson acknowledged; no reward | Seeded generator. If demolished, show recovery guidance without a cutout. |
| 3 | Inspect a worker’s strongest SPECIAL and its room match | Server `assign_correct`, `nav-dwellers`, with a client teaching acknowledgement | Claim +50 caps after reviewing; existing-state credit allowed | Choose a real matching worker. Do not require a Living-room adult to move unless a valid, safe destination is proven. |
| 4 | Build additional Living Quarters; explain current population versus housing limit | Server `build`, `build` | Successful additional construction; claim `dweller:Wanderer` | Actual price, legal footprint and enough post-build capacity for an arrival. Existing seeded housing alone must not qualify. |
| 5 | Review a healthy adult, choose duration and dispatch | Server departure objective, `nav-exploration` | Successful departure; claim +50 caps | Prefer new arrival with no production job. Default short duration; explain supplies and recall before confirming. |
| End | “Your explorer is out. Keep supplies steady and grow toward your next room.” | Client handoff | Orientation complete after departure reward is claimed | Show Briefing and background progress. No population wait or return required. |

Step 3's copy must match its contract: call it “Understand SPECIAL staffing” if it permits
existing-state credit. Do not label a ready review step “Assign a dweller” while silently requiring
no assignment. The server remains authoritative for reward eligibility; the local acknowledgement
is teaching state, not a security or reward boundary.

**Feasibility gate for a real assignment lesson:** across controlled common/rare seeds, find a
mature eligible candidate, a room matching the canonical highest-SPECIAL tie rule, and a legal
free slot; prove the transfer through the real service and UI. Ensure the candidate is not needed
to keep another production room stable. If this fails, keep the inspection version. Do not add a
new pre-build arrival to a vault already above capacity.

**Housing completion:** define an explicit target policy for additional capacity rather than
letting “one Living room exists” satisfy this step. A size-3 tier-1 room adds eight slots: separate
construction yields 16 total housing capacity; adjacent merging can yield a different total via
the capacity formula. Verify both. Credit a successful `ROOM_BUILT` extension/merge, not an
upgrade event. Permit an earlier player-built extension to qualify through persisted build progress
or an explicit additional-housing state check; GET remains read-only. Claims revalidate capacity.

### B. Growth and return visits

Population is a background dependency, not a chain of “Reach N” spotlights. Until something
becomes actionable, the Briefing owns the next useful action: address incidents, recover supplies,
review unassigned dwellers, expand housing, or enable recruitment. Avoid an empty persistent tour card.

At each unlock, announce it through the existing toast/modal plus bell flow and offer one contextual
lesson. A population threshold alone does not make construction actionable: the room may already
exist, caps may be insufficient, a footprint may be unavailable, or power may be critical.

| Chapter | Trigger and lesson | Immediate task | Wait / handoff |
|---|---|---|---|
| Growth | Housing has space and Radio exists | Inspect recruitment versus happiness mode; enable recruitment if desired | Population chip toward next unlock; probabilistic estimate only |
| Medbay, population 14 | Teach retained Stimpaks and medical staffing | Build if affordable and placeable; inspect if already built | Supplies produced in background; do not block on collection |
| Science Lab, population 16 | Explain RadAway and radiation | Build or inspect; staff when a safe eligible worker exists | Medicine stock remains background |
| Office, population 18 | Explain quests versus free-roam exploration | Build or inspect Office, review a mission and party requirements | Quest travel/completion is background; equipment shortages get guidance |
| Workshops, population 22/32 | Explain materials, recipes and equipment | Inspect an available recipe; craft only if materials and workers exist | Craft timer and rare drops remain background |
| Training, population 24+ | Explain work versus permanent stat growth | Start training only with an unlocked room and eligible worker | Completion and level milestones remain background |
| Later vault development | Equipment upgrades, schematics, veteran levels, population 50+ | Show relevant starter chapter in guide, not perpetual dim | No arbitrary first-session prerequisite |

Unlocks come from room catalog data, not duplicated frontend thresholds. Show the earliest relevant
unbuilt unlock and its unmet requirements. A previously seeded Storage or Radio room is not a new
build lesson just because its population threshold is crossed. Critical recovery may temporarily
precede the current lesson; it must not claim or reorder starter objectives behind the player's back.

### C. Expedition return

The journey chip follows the actual lifecycle: outbound/exploring → returning → arrived/reward flow.
Use server timestamps/status; duration is not automatically the full time until arrival. Recall can
change it. Without a reliable return estimate, show status rather than an invented countdown.

When a run returns, surface rewards normally and optionally offer an equipment/loot explanation.
Do not reopen first-session onboarding. Returning dwellers remain unavailable until arrival; a
failed or fatal run does not revoke an already-earned departure objective or grant another arrival.

## Guide state and presentation

Use one frontend step definition list keyed by stable step IDs and server `template_key` values.
The backend owns server-objective order and claims; the frontend owns explanatory taps, anchors,
and presentation. Derive ordering from server `sequence`; avoid a second hard-coded numeric map.

Each step resolves to one of these presentation states:

| State | Behavior |
|---|---|
| Loading / unknown | Preserve position, no cutout or assumed completion; retry data reads |
| Actionable | Show one action card; dim only around a visible, meaningful target |
| Teaching acknowledgement | Explain already-achieved state; allow deliberate Continue/review |
| Ready to claim | Prefer claim card over repeating an action; preserve reward text from snapshot |
| Waiting / locked | Background chip plus reason; no dim or forced navigation |
| Recoverable blocker | Explain actual blocker and link to the existing remedy; no reward mutation |
| Claimed / locally acknowledged | Move to the next eligible lesson |
| Skipped / orientation finished | Close tour; keep ordinary guide, claims and Briefing accessible |

Skipping a non-actionable spotlight is a presentation decision, not permission to claim a later
server starter step. Current backend evaluators and claims only permit the lowest unclaimed starter
sequence. Do not implement “skip locked steps” as out-of-order server progress. Contextual inspection
hints can appear independently; reward-bearing chapters retain server ordering.

Persist welcome, tap acknowledgements and skip per vault and tour version using the existing
`onboarding:v1` storage family. Migrate old state without undoing skips. Replay from Help resets
only teaching state, never server claims. If storage is unavailable, use session memory; server
rewards remain correct. Cross-device tap sync is outside the initial scope; completed server steps
prevent a repeated welcome after local-storage loss. Loading one vault must not reuse another's state.

“New vault” must be identified deliberately, not just `sequence === 0`: existing vaults can also
have an untouched first objective. Use the successful creation flow to opt into automatic welcome,
with a persisted local marker; existing vaults can launch Help. Boosted vaults skip automatic starter
orientation, consistent with their current objective assignment policy.

Taps must work with keyboard, touch and pointer. Provide Continue when an anchor is informational
rather than an existing control. Do not attach a document-wide click handler that mistakes unrelated
clicks for completion. Navigation to Dwellers is not proof of reviewing SPECIAL; opening Exploration
is not proof of dispatch. Clear target listeners on step/vault changes and unmount.

Missing/hidden/off-screen targets get an ordinary card and an explicit navigation action. Resolve
anchors after rendering and route changes; handle scroll/resize. Do not automatically scroll or
navigate on polling. Pause visual emphasis while a dialog is open, prevent focus theft, honor reduced
motion, and keep overlays out of the way of confirmation buttons and small-screen navigation.

Refresh after successful claims and actions as well as route changes/polling. A dispatch can succeed
while a read fails: show success, allow retry, and reconcile server progress without redispatching.
Double claim, stale tabs, back navigation, refresh and slow network must converge to one reward.

## Background chips

Keep at most three concise chips; each opens an existing relevant screen. They remain available
through the Briefing after orientation ends and do not disappear merely because no spotlight is active.

- **Housing:** `Dwellers 11/16`. Distinguish this from **unlock progress:** `Medbay at 14 · 11/14`.
  Housing capacity and next-unlock threshold are different denominators. Initial `10/8` is real;
  explain “Build housing to welcome more dwellers,” rather than clamp the display to 100%.
- **Exploration:** status and a reliable approximate return time; aggregate several runs instead
  of flooding the screen. Expired estimates trigger refresh/status text, never negative timers.
- **Recruitment:** only when Radio exists. Show recruitment mode, capacity blockers, and a
  dynamic average estimate from recruitment stats. Say “average,” not “arrives in.” If mode is
  happiness, offer an explicit switch; expanding housing must not silently change the mode.

Do not invent APIs for information already in vault, room, exploration or Radio stores. Load missing
required data explicitly; missing data must not be mistaken for zero population/no active operation.
Avoid new polling loops per chip. Keep notification preferences and critical-alert behavior intact.

## Backend contracts and reward safety

1. **Departure:** prefer a distinct `explore` objective type for wasteland dispatch; keep existing
   `expedition` quest-completion objectives unchanged. Emit `DWELLER_DEPARTED` once per successful
   exploration from the shared `_persist_departure` path, after departure is committed. Include
   vault, exploration ID and member IDs; a party counts as one run. Failed validation/commit emits
   nothing. Do not reuse `DWELLER_ASSIGNED` as a departure signal.
2. **Reconciliation:** define read-only/claim-time credit from persisted explorations so a missed
   in-memory event or a dispatch before the step became current cannot strand the player. Match
   the declared completion policy; completed/returning runs can prove departure, quests cannot.
   Queries belong in CRUD. Inspect retry/idempotence rather than building a general event system.
3. **Arrival:** phase 1 uses `dweller:Wanderer` alone on the housing claim. Additional +50 caps
   is optional later work, requiring atomic bundle settlement, snapshot and display support.
   Generated arrival must be adult, alive, healthy, unassigned and eligible for exploration.
4. **Atomic claim:** housing reward creation and completion flag settle together under the vault
   lock. Full capacity, failed creation or database errors leave the reward unclaimed. If another
   recruit fills the last slot first, show “Build more housing to claim”; never discard the reward.
   Concurrent/repeated claims create at most one arrival. Announce the arrival and refresh roster,
   population, capacity and objective state; preserve collection-event suppression for rewards.
5. **Credit policy:** explicitly distinguish existing-state lessons from new-action lessons. The
   housing reward requires additional housing and available capacity. Assignment inspection can
   credit existing staffing. Avoid blanket disabling state credit needed by historical chapters.
6. **Identity/types:** expose `template_key` in objective reads, CRUD projection and frontend types.
   Include `explore` in the frontend type/action mapping so it routes to Exploration, not Quests.
   Regenerate API types after API changes. Respect current 32-character challenge/reward limits;
   put longer lesson copy in descriptions rather than relying on unchecked ORM insertion.
7. **Enums:** `GameEvent` is currently an in-memory `StrEnum`, not a mapped PostgreSQL enum.
   Adding its member alone does not need a PG enum migration/snapshot edit. Inspect actual mapped
   enum changes before applying that rule; catalog/link/schema changes still need migrations.

## Economy and placement sanity checks

For the intended untouched seed, with arrival-only housing reward:

| Action | Caps delta | Caps remaining | Population / housing |
|---|---:|---:|---|
| Start | — | 1000 | 10/8 |
| Staffing lesson claim | +50 | 1050 | 10/8 |
| Build separate size-3 Living room | −150 | 900 | 10/16 |
| Claim arrival | 0 | 900 | 11/16 |
| Dispatch claim | +50 | 950 | 11/16; verify away-dweller population semantics |

Prices are category-based. Seeded Production includes Radio, so Medbay is **400 + 4×100 = 800**
before additional production builds. Science Lab after Medbay is **900**. The 950-caps orientation
balance therefore does not fund both, let alone a 1000-base Office. Later chapters need real income
or explicit, reviewed rewards; population unlock alone cannot guarantee affordability.

The Office catalog has no incremental cost while `get_room_build_price` currently rejects a missing
or zero increment. Trace the full build path and reproduce this potential blocker before declaring
Office onboarding feasible; the catalog's 1000 base price is not proof of a successful build.

For every construction lesson check a legal size/coordinate, elevator access, overlap, uniqueness,
merge behavior, full grid and actual quoted cost. Player-built unrelated rooms can change costs.
Do not copy Phase 0's 150 caps into actionable checks. If the player spends caps elsewhere, the guide
shows the unmet requirement and an available earning path without promising a timed payout.

Resource validation must use the full seed: infrastructure, Radio, housing, actual SPECIAL, elder
and apprentice modifiers, youth consumption, added housing, arrival and selected expedition member.
Run snapshots at start, after build, after arrival and after departure, plus a delayed 20-minute
active playthrough and a return after inactivity. Report minimum stocks, net rates, warnings,
time-to-zero and recovery—not just final resources. Never certify safety from the three-room
uniform-worker CLI alone. If necessary, extend its scenario input in a later test-backed task.

## Migration and existing vaults

A catalog rewrite alone does not update production templates or their assigned links. Do not
rename/reorder old rows in place and assume earned progress still means the same thing.

Recommended transition:

- Introduce the revised orientation templates with stable version-qualified keys where semantics
  change. Reuse a key only when completion and payout semantics remain compatible.
- Preserve completed links and historical payouts. Preserve ready/progressed legacy tasks with their
  original totals and frozen rewards; keep them claimable through the guide. Never convert old
  collection progress into a departure or replace an earned caps payout with a capacity-gated dweller.
- New standard vaults receive the revised orientation plus later authored chapters. Legacy vaults
  retain their existing ordered guide and receive optional explanatory replay, without automatic welcome
  or a second starter reward track. Boosted vault assignment remains unchanged.
- If the product chooses to retire unfinished legacy steps too, specify explicit per-link mapping and
  cohort eligibility before migration. Retire only untouched tasks under that policy, and ensure any
  retained earned task remains claimable despite ordering changes. No silently deleted rewards.
- Version eligibility must persist server-side if catalog selection differs between old and new vaults;
  local storage cannot decide reward entitlement. Choose the smallest explicit schema/catalog marker
  that implements this policy, with a backfill for existing rows in the same migration.
- Use stable keys first, canonical `LOWER(TRIM(name))` fallback for pre-key rows; preserve custom
  templates and IDs. Make changes idempotent, keep one Alembic head, and document downgrade as a
  no-op where reversal would erase progress. Snapshot payouts before changing earned templates.

A deployment must coordinate catalog seeding, migration and API/frontend compatibility. Do not serve
new keys/types to a frontend that cannot resolve them. Validate the migration against representative
production-like old rows before enabling automatic orientation for new vaults.

## Implementation sequence and exit gates

| Phase | Work | Exit evidence |
|---|---|---|
| 0 — feasibility | Confirm staffing lesson choice, extra-housing credit, legal placement, Radio mode, Office build, population semantics and full-seed resources | Recorded real-service results across controlled seeds; blockers resolved or explicitly kept out of launch |
| 1 — contracts | Test-first departure emission/evaluator/reconciliation; housing credit and capacity-safe arrival claim; objective keys and frontend routing | Regression tests pass; no quest regression; one arrival per claim; generated API types match |
| 2 — catalog transition | Revised templates, legacy eligibility/link policy, later chapter preservation and idempotent migration | Migration tests for cohorts and earned snapshots; fresh and migrated catalogs select the intended current step |
| 3 — presentation | Ordered taps, staffing review, actionable selection, background chips, Help/skip/replay and recovery cards | Component tests plus keyboard/mobile walkthrough; no spotlighted waits or stale targets |
| 4 — full journey | Real vault creation → housing → claim → dispatch → exit/reload → return; unlock/Briefing chapters | Timing and resource evidence; old/boosted vaults unaffected; no reward loss |
| 5 — rollout | Coordinate docs/game-domain rules, compatibility and release validation | Required lint/types/tests green; reviewable diff and playtest record; no push/merge without explicit approval |

Keep batches small. Business logic stays in services, queries in CRUD, endpoints thin; frontend
retains Store → Service → API. Write failing regressions before bug fixes. Load matching repo skills
when implementing each batch. Do not widen into unrelated balance or UI-system migrations.

## Required sanity-check matrix

| Scenario | Expected result |
|---|---|
| Fresh standard common/rare seeds | Complete orientation without an assumed SPECIAL, rare drop, recruit roll or expedition return |
| Already-correct workers | Review explains match; deliberate acknowledgement; no forced unsafe transfer |
| No matching free assignment slot | Inspection fallback or concrete recovery; never “auto-assign” that must fail |
| Existing seeded housing | No free additional-housing claim at 10/8; no capacity-conflict loop |
| Separate build / adjacent merge / early out-of-order build | Both capacity paths credit correctly; earned state survives claim/reload |
| Full capacity at claim / concurrent Radio recruit | Reward stays available; capacity remedy shown; one arrival at most |
| New arrival | Adult, healthy, unassigned; appears in actual departure picker |
| Successful solo / party / targeted / free-roam departure | One qualifying run; server objective ready; quest objectives unchanged |
| Validation/commit failure / empty party | No departure progress; no false success |
| Lost event / early departure / refresh failure | Persisted state reconciles; no duplicate send or reward |
| Return, recall, death | Departure stays earned; lifecycle text and availability remain correct |
| Housing expanded after full-vault Radio switch | Hint reflects actual mode; player can explicitly enable recruitment |
| Population reached but caps/placement/power missing | Undimmed reason/remedy; no impossible build spotlight |
| Existing Medbay/Office or multiple unlocks | Inspect existing system or choose next relevant lesson; no duplicate build requirement |
| Incidents / critical resources / player dialog | Recovery/dialog has priority; tutorial resumes without lost progress |
| Skip / Help replay / storage reset / two vaults / two tabs | Teaching state isolated; server claims never reset; no duplicate welcome after server completion |
| Legacy paid / ready / partial / untouched / custom rows | Original entitlement and intended ordering preserved; migration rerun adds nothing |
| Boosted vault | No forced starter tour or changed starter reward entitlement |
| Keyboard / touch / small screen / reduced motion / absent target | Continue/navigation usable; no trapped focus, obstructed confirmation or stray dim |
| 20-minute active / slow tour / inactivity return | Full-seed stocks and recovery verified; no undocumented tutorial-induced collapse |

Use the real SQLite/fakeredis services and factory builders for backend behavior, with PostgreSQL
integration where locking/migration behavior demands it. Stub only external systems and the clock.
Frontend tests cover selection and rendering, not just copied step constants. Run relevant suites,
architecture guards, lint/type checks, changed-file Python typing, migration checks and regenerated
API types. Broaden validation only for new failures or unresolved risks.

## Manual playtest script and launch record

1. Create a standard vault with the production catalog. Record seed/RNG, caps, population, housing,
   resource stocks/rates, room occupancy, Radio mode and every candidate's eligibility.
2. Start using keyboard and repeat on narrow touch layout. Open power and the generator; review a
   real worker. Record time/actions per lesson and any ambiguous instruction.
3. Build separate housing, claim the arrival and dispatch it without moving a production worker.
   Repeat with adjacent merging and construction before the relevant server step becomes current.
4. Delay claim, fill capacity, attempt another claim in a second tab, and retry after adding space.
   Reload during dispatch/read failure. Verify one arrival, one run and one payout.
5. Skip/replay, switch vaults, leave and return. Confirm Briefing/chips survive the orientation handoff.
   Simulate recall/return and population 14/16/18 with affordable and unaffordable construction.
6. Repeat on migrated and boosted vaults. Audit original ready rewards and partially progressed tasks.
7. Capture the full-resource snapshots at 0/5/10/20 minutes, minimum stocks, warnings and recovery.

Launch record must state which checks actually ran, results, remaining blockers, migration cohorts,
and first-session duration. Do not label unexecuted scenarios “verified.” Do not deploy merely because
isolated departure tests pass.

## Decisions to settle before feature work

Recommended defaults are explicit so routine implementation does not need repeated permission:

- First release: staffing **inspection + existing-state claim**, not guaranteed Living-room reassignment.
- Housing reward: **arrival only**; combined caps payout is optional scope.
- Departure: **distinct `explore` type**, persisted-run reconciliation, existing quest behavior preserved.
- Welcome: automatic only from new standard-vault creation; optional Help for existing/boosted vaults.
- Skip/replay: per vault and tour version; server rewards unaffected.
- Short orientation ends at the departure claim; later chapters and chips continue without persistent dim.
- Preserve legacy reward contracts; do not delete the post-Office guide just to shorten orientation.

Still requiring evidence: assignment UI feasibility if a real transfer remains desired; extra-housing
credit and merge totals; complete-seed resource stability; Office price/build path; away-dweller
population counting; and production-like migration cohort selection. These are implementation gates,
not assumptions to hide in copy.
