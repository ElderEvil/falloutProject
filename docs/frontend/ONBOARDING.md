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
| End | “Keep supplies steady and grow toward your next room.” Mention the explorer only if a run exists | Client handoff | Default path ends after departure claim; locally skipped lessons can end teaching earlier | Show Briefing and background progress. Pending rewards remain in Starter. No population wait or return required. |

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

## Per-step “Skip step”

### Contract and controls

Every teaching card offers **Skip step**, alongside Continue or its relevant action. Keep
**Skip tour** as a separate, quieter control; on the welcome card it remains the whole-tour exit.
On a ready objective card, Claim stays the primary action and Skip step remains available.
Disable conflicting controls while a claim is in flight, so a successful response cannot advance
the wrong teaching card. Skipping requires no confirmation or network request.

Skip step dismisses this explanation for this vault and advances the **teaching** cursor. It does
not claim, complete, delete, waive, reset, or forfeit a server objective. No reward is granted, and
no API permission/order rule changes. A tap lesson is locally skipped; an objective-backed lesson
is locally skipped while its objective remains in Starter. Use the helper text “Skips this lesson.
Your objective and reward stay in Starter.” Provide a brief Undo action that restores this lesson
only if it is still relevant; do not reset other lessons or server state.

The lesson selector must therefore stop using the current server objective as its only cursor.
Select the first relevant unacknowledged/unskipped teaching entry whose action can be taken now.
Server order still decides which rewards may be earned/claimed. When all orientation lessons are
acknowledged or skipped, close the tour and hand off to the Briefing even if server rewards remain.
The permanent Starter surface must still identify the current claimable server step.

### Dependencies when a lesson is skipped

| Player choice | What the guide does next | What stays pending |
|---|---|---|
| Skip the power-bar or generator explanation | Move to the next eligible teaching entry | Nothing on the server; no reward involved |
| Skip SPECIAL review | Offer the housing lesson if affordable and placeable | Staffing reward remains current in Starter; early housing construction must reconcile later |
| Skip housing explanation | Offer departure only if a suitable adult can be sent safely | Housing objective and arrival reward remain; never pretend Wanderer exists |
| Skip a ready reward card | Hide this teaching card; show a quiet “Reward waiting in Starter” affordance | Earned payout stays intact; later ordered rewards may require this claim first |
| Skip departure explanation | End short orientation; contextual help remains available | Departure objective stays available; no run is dispatched |
| Skip every orientation entry | Briefing and normal play continue immediately | All server contracts, claims and critical alerts remain unchanged |

Departure eligibility uses the real policy, not “idle only.” A healthy resting adult may be a
safe candidate; never silently remove the only essential production worker to manufacture one.
If no safe candidate exists after skipping housing, hide the departure spotlight and show a
non-dimming explanation/link to housing or the pending arrival claim. That is a recovery action,
not a reappearance of the skipped explanation. Do not call it a completed departure lesson.

When a later lesson's reward is blocked by an earlier unclaimed objective, explain “Claim your
earlier reward in Starter first” and link there. Do not enable a claim that the backend will reject,
auto-claim multiple steps, or reopen the skipped spotlight. Building and dispatching out of order
must reconcile through the backend rules already specified above; this is a dependency of shipping
Skip step, not an exception to current-only event counters.

### State and recovery

Extend `useOnboardingState` with stable per-lesson statuses (`acknowledged` / `skipped`), scoped
by vault and teaching version. Absence means unseen; do not store a separate redundant next index.
Keep whole-tour suppression separate. Existing `skipped: true` remains a whole-tour choice after
migration. A single Skip step must never set it. Use IDs such as `orientation.resources` rather
than sequence numbers, challenge text or DOM selectors.

Store status only on deliberate acknowledgement/skip, not on rendering, polling, route entry,
claim failure, or an API response merely proving an objective is earned. Reload/route changes and
multiple mounted consumers must converge on the same ledger. Missing storage falls back to session
state; it cannot affect rewards. Relevance is recomputed from live data, never saved as truth.

Help offers **Resume guide**, **Replay orientation**, and **Reset first-time hints** with explicit
scope to the selected vault. Resume continues unseen entries without clearing skips. Replay clears
orientation teaching statuses and explicitly enables teaching replay; it works after all server
steps are claimed and never pays them again. Reset hints clears only the contextual ledger.
Avoid promising replay if the implementation only clears the whole-tour skip flag. Replay does
not need to mark an old vault newly created to show an introductory explanation.

## Curated first-time mechanic triggers

### Purpose and initial set

First-time hints explain a mechanic when the player encounters it in a meaningful context. They
are small inline cards or anchored popovers with Continue / Skip step, normally **without dim**.
They do not create objectives, grant rewards, force navigation, dispatch anything, or gate actions.
Feature unlock announcements and earned-reward notifications keep their existing independent flow.

Start with this finite authored set; do not attach automatic tours to every tab, click or event.
The trigger is a semantic UI action plus eligible live state. A trigger adapter may run on panel
entry, but ordinary DOM insertion or background fetching must not enqueue lessons.

| Mechanic ID | First meaningful trigger | Explain | Eligibility / suppression |
|---|---|---|---|
| `resources` | Player opens the resource explanation or generator details | Stock versus capacity, net trend, production is automatic | Share completion with orientation resource lessons; critical recovery takes priority |
| `special-staffing` | Player opens a worker's SPECIAL/assignment controls | Strongest stat, room match, slot and age constraints | Show actual candidate/room data; no transfer required; share orientation acknowledgement |
| `housing-build` | Player selects Living room in the build menu | Capacity versus population, quoted cost, legal placement and merging | Once per vault; explain before committing; share orientation housing lesson |
| `exploration-departure` | Player opens a valid send-duration/party preview | Duration, supplies, staffing impact, return/recall lifecycle | Eligible adult and loaded preview; never require supplies absent from storage; share orientation lesson |
| `radio-recruitment` | Player opens Radio controls while recruitment is relevant | Recruitment versus happiness, space requirement, average arrival estimate | Actual Radio exists; describe current mode; no guaranteed countdown or silent switch |
| `medical-treatment` | Player opens treatment controls for an injured/irradiated dweller | Stimpaks heal; RadAway removes radiation; actual applicability | Relevant condition and controls loaded; don't obstruct urgent treatment or invent available stock |
| `loot-equipment` | Player opens returned loot or an equipment slot with an available item | Keep/equip/sell choices and stat effects | Wait until reward modal closes for optional help; do not claim or equip automatically |
| `quest-party` | Player selects an available mission in the Office | Requirements, party roles/equipment and quest travel versus free roam | Office/mission exists; explain missing requirements directly; no quest-completion wait |
| `training-start` | Player selects a training room or opens a training preview | Permanent stat gain, worker availability, background timer | Unlocked room and real preview; no spotlight on completion wait |
| `crafting-recipe` | Player opens a known recipe with its material requirements | Materials, recipe/stat requirements and crafting timer | Relevant workshop exists; missing materials are explained without implying crafting is ready |

Defer separate scrapping, breeding, arena and advanced progression lessons until the initial set
is validated. The scrapping lesson, when added, belongs **before** destructive confirmation and
must explain schematic eligibility without implying a guaranteed result. This planning scope
does not change those mechanics or their existing confirmation dialogs.

### Trigger lifecycle and arbitration

Use one small authored definition list for mechanic ID, eligible context, copy and preferred anchor.
Wire explicit calls from existing successful action/preview flows rather than a global event bus
or watchers over all stores. Reuse the guide shell and state helper where appropriate; do not build
a generic rules engine, new notification category, analytics platform, or parallel polling system.
Keep business operations in their existing module services/stores; adapters report teaching context.

The resolver uses this order: urgent incident/treatment → player confirmation/reward dialog →
active orientation lesson → optional first-time hint → background chips. A hint never opens a
second modal, steals focus, hides a claim, or closes another dialog. If its natural home is an
inline region in the currently opened panel, show it there without a separate overlay.

Only one optional hint is visible at a time. Keep at most one deferred eligible context in memory;
recompute it after the current card closes. Prefer the screen the player is using, discard stale
contexts on navigation, and leave other mechanic IDs unseen so they can trigger naturally later.
Do not enqueue every lesson after an unlock or play old hints in a burst on login. Until a hint is
acknowledged or skipped it may recur at a later meaningful encounter, but not repeatedly in the
same open panel/session after a temporary close.

Natural actions may satisfy a teaching lesson even when it was not displayed: a confirmed dispatch
proves the departure action was understood sufficiently for orientation. Record that acknowledgement
from a successful response or persisted historical state, never from clicking Send or a failed
request. Explanations remain available from Help. A failure can show existing validation copy,
but it must not mark the mechanic seen or change its reward progress.

### Dedupe and player choice

Orientation and contextual hints share mechanic IDs through an explicit mapping. Acknowledging
or skipping the SPECIAL lesson suppresses the same mechanic's first-time popover; it does not
suppress unrelated housing or exploration help. Resource bar and generator explanations count
as separate orientation entries but jointly satisfy the resource mechanic explanation once both
are acknowledged/skipped. The central status ledger prevents duplicate presentations in one vault.

Whole-tour Skip suppresses orientation only, preserving the current meaning of that button.
Offer a separate **First-time mechanic hints** setting for optional contextual help; clearly state
that it remains enabled when the player skips orientation. Turning it off closes/dequeues optional
hints without clearing their ledger or changing critical alerts. Skipping an individual hint
records only that mechanic as skipped. This setting is distinct from notification preferences.

Automatic triggers initially target new standard vaults with the creation marker. Existing/boosted
vaults can opt in through Help; don't spring ten “first-time” cards on established players after
deployment. In opt-in mode use persisted operations where available to mark already-used mechanics
acknowledged, and otherwise call the hint an explanation—not proof that this is their first use.
Local storage cannot guarantee lifetime first-use behavior across devices; cross-device persistence
is outside the initial scope. Do not fabricate historical usage from a newly mounted component.

Changing a lesson's wording does not reset its status. Version the teaching contract only when
behavior materially changes, and preserve old whole-tour/hint opt-outs. Help can replay a single
mechanic without resetting other hints, claims, or the current server guide.

### Build order and sanity checks for these additions

1. Define the teaching IDs, orientation-to-mechanic mapping and state migration in the existing
   state helper. Verify reset scopes and per-vault isolation before wiring UI.
2. Implement teaching selection independent of current server objective, then Skip step/Undo and
   pending-reward affordance. Integrate only after early build/departure reconciliation is sound.
3. Wire the four orientation-overlapping triggers first: resources, SPECIAL, housing and departure.
   Check dedupe by entering through the tour, existing controls, and Help in different orders.
4. Add Radio, medicine, loot, quests, training and crafting as a second reviewed batch, using
   existing panels/previews. Finish hints setting and single-mechanic replay.
5. Verify keyboard/touch activation, small screens, absent anchors, dialog priority, stale contexts,
   claim failures, refresh, two tabs, two vaults, storage failure and whole-tour/hints opt-outs.

Specific acceptance scenarios: skip a ready staffing reward then build; skip housing with and
without a safe explorer; dispatch before earlier claims; skip every lesson; replay after all rewards
are claimed; open the same preview repeatedly; trigger two mechanics while a reward modal is open;
disable hints mid-card; reload between Skip and Undo; and open Help in an existing/boosted vault.
Each must preserve server order and earned rewards, avoid repeated dim/popovers, and leave a clear
route back to relevant help. Tests/playtests are planned validation, not evidence already collected.

## Implementation detail: Skip step and mechanic hints

This section is the delivery checklist for the two additions above. All contracts here are
proposed implementation requirements, not a claim that the current worktree implements them.
Choose names to fit existing code, but preserve the state boundaries and observable outcomes.

### 1. Authored definitions and ownership

Extend the existing progression module; use its `models/` for the ordered authored definitions
(`onboardingSteps.ts`) and `composables/` for teaching selection. Keep the already shared
`core/composables/useOnboardingState.ts` as the persistence owner. Avoid introducing another
Pinia store or event bus solely for hints. Reuse installed UI components and existing routes.

Each authored teaching definition needs: stable lesson ID, kind (`tap`, `inspection`,
`objective-explanation`), mechanic ID, short title/body, optional objective template key,
preferred anchors, relevant action route, and a named eligibility check. Explicitly map the
two resource explanations to one mechanic; do not infer this from similar titles or selectors.
The finite definition list is the only source of teaching order. The backend catalog remains
the only source of reward order, completion targets and payouts.

Keep eligibility functions pure: give them a loaded snapshot of vault, rooms, dwellers,
objectives, active runs and teaching state. Return `eligible`, `blocked` with a reason, or
`unknown` if required data is missing. No fetch, DOM query, mutation, clock scheduling or
reward claim belongs inside lesson selection. Resolve anchors in the view after selection.

### 2. Persisted state and commands

Preserve existing `created`, `welcomed` and whole-tour `skipped` flags. Add a versioned teaching
record per vault containing only stable IDs and player choices:

```ts
type LessonStatus = 'acknowledged' | 'skipped'

interface TeachingState {
  version: 1
  lessons: Partial<Record<LessonId, LessonStatus>>
  mechanics: Partial<Record<MechanicId, LessonStatus>>
  hintsEnabled: boolean
  contextualOptIn: boolean
  replayOrientation: boolean
}
```

The existing vault record owns this teaching record; missing IDs are unseen. The illustration
does not require duplicating equivalent status: derive orientation-covered mechanic state from
the explicit mapping, and persist mechanic status only for direct contextual choices. Explicit
single-mechanic replay can override mapped suppression for that one invocation without deleting
the original lesson history. Keep active card, pending context, request generation and Undo in
memory; never persist DOM references, server progress, blockers or timer deadlines.

Provide narrowly scoped commands in the state helper:

| Command | Mutation | Must preserve |
|---|---|---|
| Acknowledge lesson | Set that lesson to acknowledged | Other lessons, whole-tour choice, claims |
| Skip lesson | Set that lesson to skipped | Server state, unrelated mechanics, hints setting |
| Skip mechanic | Set direct mechanic status to skipped | Other lessons and mechanics |
| Skip tour | Set existing whole-tour suppression; close orientation | Hint opt-in and individual history |
| Resume guide | Clear whole-tour suppression only | Individual acknowledgements/skips, claims |
| Replay orientation | Clear orientation lesson statuses, explicitly enable replay and clear tour suppression | Direct contextual statuses, creation marker, hints setting, claims |
| Replay one mechanic | Open that explanation on demand without resetting unrelated state | Whole-tour choice, saved acknowledgements, claims |
| Reset first-time hints | Clear direct contextual statuses and enable an explicit fresh hint pass | Orientation lesson statuses, claims; mapped orientation lessons still dedupe |
| Disable hints | Set hintsEnabled false; close optional card and deferred context | All saved statuses, orientation, critical alerts |

Default hints to enabled for newly created standard vaults; require explicit contextual opt-in
for existing/boosted vaults. Store this choice per vault in the initial release, and label that
scope in Preferences. Missing legacy teaching records migrate lazily with empty ledgers;
`skipped: true` still hides the tour. Preserve the vault record when resetting a subsection.
Malformed/unsupported local data must not crash vault rendering: treat only that teaching
subrecord as unavailable, retain recoverable opt-outs, and keep a working session fallback.

### 3. Selection, progression and reward controls

For each render, filter locally acknowledged/skipped entries, derive mechanic dedupe, then
choose the first relevant eligible lesson. If all remaining entries are temporarily blocked,
show a concise undimmed blocker or the Briefing; do not mark them skipped/completed. If all
entries are acknowledged/skipped, close orientation. Explicit replay allows explanation of
completed server steps; already-claimed steps never show a second reward action.

Snapshot the vault ID and lesson ID when handling Continue, Skip or Claim. Ignore delayed
responses/actions if their context no longer matches the active vault/card. A repeated click
is idempotent. Selection changes, navigation and background polling never count as acknowledgement.
For inspection, require the relevant detail panel or a deliberate Continue; opening Dwellers
alone is insufficient. For natural actions, acknowledge only after successful build/dispatch
settlement; best-effort refresh failure does not turn a successful action into a failure.

Separate `earned`, `currentServerStep`, `claimed`, and `teachingDismissed`. A lesson may be earned
but not currently claimable because an earlier server step remains. Display Claim only when
earned, unclaimed and permitted by server order; otherwise show an explanation/link to Starter.
The backend revalidates every claim. Never use local skipped state to infer server eligibility.
Retired earned rewards remain independently claimable under the retirement policy.

After a successful claim refresh objectives, vault values and affected roster/items using
existing actions. Do not postpone the success feedback until every refresh finishes. Keep a
visible retry path for failed reads; do not resend a successful claim/build/dispatch. Claim
failure stays visible in the same card and leaves teaching/reward state unchanged.

### 4. Controls, Undo and accessibility

Use the existing Button primitive. Skip step is a secondary text/ghost control; Skip tour is
visually separate. Give the card a stable accessible name and concise live announcement when
its lesson changes. Do not focus it automatically after polling or background events. If a
focused button disappears after an explicit action, move focus to the replacement card's
heading/action or its persistent guide launcher. Keyboard and touch must work without dragging.

After Skip step, show “Step skipped · Undo” in an inline guide status area for eight seconds.
The current toast helper has no action support; do not extend it just for Undo. Keyboard focus
or pointer hover pauses expiry, and Help remains the non-timed recovery route. Undo is scoped
to the captured vault/lesson and restores its prior local status only if still unchanged.
Navigating to another vault, skipping another lesson, claiming that lesson, or acknowledging it
elsewhere invalidates the old Undo. After reload there is no stale Undo timer to recover.

With an open confirmation/urgent dialog, hide spotlight emphasis and defer optional popovers;
inline explanations inside the owning panel may remain. A missing or zero-size anchor never
creates a cutout. Give navigation/Continue instead. Don't automatically scroll to a target,
and don't let a fixed guide cover the current confirmation action at narrow widths.

### 5. Integration points for first-time hints

| Existing surface | Adapter placement | Completion signal / data refresh |
|---|---|---|
| Resource bar and generator details | After user opens the explanation/detail | Explicit Continue; live stock/capacity/rates already loaded |
| Dweller SPECIAL/equipment details | After relevant detail content resolves | Explicit acknowledgement or successful matching assignment/equip |
| `RoomMenuItem` / build selection | Parent handles selected Living room, not every list render | Successful `room` store build response; quoted cost/placement from real builder |
| `useSendToWasteland` | Valid preview opened; use inline explanation in duration modal | Confirmed dispatch response; same behavior for detail page, map and wasteland entry |
| `RadioControls` | User opens its controls with current stats loaded | Acknowledgement; mode changes only through existing explicit action |
| Medical controls / `dwellerMedical` | User enters treatment preview for a relevant condition | Acknowledgement or successful treatment; never defer urgent treatment for teaching |
| `useExplorationFinish` / `DwellerEquipment` | After reward presentation finishes or available equipment preview opens | Acknowledgement or successful equip; actual awarded inventory |
| Office mission/party preview | User selects mission and requirements load | Acknowledgement or confirmed departure; no quest-completion trigger |
| `TrainingRoomModal` | Room/candidate preview is ready | Acknowledgement or successful training start; no completion timer required |
| `CraftingPanel` | Recipe selection and material requirements resolve | Acknowledgement or successful start; failed craft leaves lesson unseen |

Use one shared presentation resolver rather than duplicating suppression logic in each surface.
Adapters pass a typed mechanic ID, vault ID, owning route/entity and existing loaded context.
Keep callbacks local to the existing module boundary; do not make API services depend on DOM
anchors. Shared entry paths such as wasteland sending must call the same adapter once.

Deferred hints retain only identity/context while that route/entity remains relevant. On release
of the foreground card, recheck opt-outs, ledger, data readiness and entity existence before
showing them. Only one hint may render; stale/unselected hints remain unseen for their next
natural trigger. “Shown” is an in-memory suppression state for the current encounter, not a
persistent acknowledgement. Temporary dialog dismissal does not complete a mechanic.

## Acceptance checklist for Skip step and mechanic hints

Use these IDs in implementation notes and review evidence. An acceptance ID passes only when
the observable outcome is verified; implementation-shaped mocks alone do not establish it.
The checks below are planned, not executed as part of this documentation task.

| ID | Given / when | Required observable result |
|---|---|---|
| SK-01 | Active tap lesson; choose Skip step | Next eligible teaching entry appears; only this lesson is saved as skipped; no network mutation or payout |
| SK-02 | Earned staffing reward; skip its card | Reward remains unclaimed with its original payout in Starter; housing explanation may appear; no auto-claim |
| SK-03 | Build housing after skipping staffing, then claim staffing | Additional construction is recognized without a second build; housing reward becomes eligible in server order |
| SK-04 | Skip housing with no safe adult available | No departure dim or impossible Send instruction; undimmed housing/arrival remedy available |
| SK-05 | Skip housing with a safe resting adult available | Departure teaching may appear; no invented arrival, automatic unassignment or dispatch |
| SK-06 | Dispatch before earlier reward claims | Persisted run reconciles when departure becomes current; eventual reward paid once; quest counters unaffected |
| SK-07 | Skip every orientation lesson | Tour closes; Starter claims, Briefing and critical alerts remain accessible |
| SK-08 | Click Skip twice or press Enter repeatedly | One local transition; unrelated lesson statuses and rewards unchanged |
| SK-09 | Claim is in flight; attempt Skip/route switch | Conflicting controls disabled; stale response cannot advance or mutate another vault's teaching state |
| SK-10 | Undo before expiry in the original unchanged context | Only skipped lesson restored; no payout replay or unrelated state reset |
| SK-11 | Reload/switch vault/complete lesson before old Undo | No stale Undo can undo newer decisions or affect another vault |
| SK-12 | Resume guide after whole-tour skip | Resume remaining unseen entries; individual skipped lessons stay skipped |
| SK-13 | Replay after every orientation reward was claimed | Explanation cards work; no new objectives, claim buttons or payouts; creation marker preserved |
| SK-14 | Claim fails due to full housing or stale order | Error visible; reward and teaching status unchanged; appropriate recovery/link offered |
| ST-01 | Legacy storage has only skipped/welcomed/created | Lazy migration preserves those values and whole-tour suppression; no forced welcome |
| ST-02 | Storage unavailable/corrupt; acknowledge a card | Vault remains usable with session state; server claims unaffected; no unhandled rendering failure |
| ST-03 | Two vaults and multiple mounted consumers | Choices isolated by vault; all consumers agree on current ledger; switching does not display the previous vault's hint |
| TR-01 | Open relevant preview with its data still loading | No guessed copy/actionability; hint becomes eligible only after required data resolves |
| TR-02 | Open the same eligible panel repeatedly | At most one hint per open encounter; acknowledgement/skip prevents future automatic repetition |
| TR-03 | Skip/acknowledge orientation SPECIAL, then open assignment controls | No duplicate SPECIAL popover; other mechanic hints remain eligible |
| TR-04 | Only one resource orientation entry acknowledged | Other resource entry remains available; joint resource mapping resolves only after both are handled |
| TR-05 | Two hints trigger during a reward/confirmation dialog | No second modal, focus theft or dim; at most one valid context reconsidered after dialog closes |
| TR-06 | Navigate away or entity disappears while a hint is deferred | Deferred hint discarded; mechanic remains unseen; no detached target or wrong-vault copy |
| TR-07 | Cancel/fail dispatch, training or crafting | No success-derived acknowledgement or server progress; normal validation remains visible |
| TR-08 | Action succeeds but its follow-up read fails | Success remains reported once; retry reads without repeating action/reward |
| TR-09 | Disable first-time hints while a hint is open | Optional hint/deferred context closes; saved ledger, orientation and critical alerts unchanged |
| TR-10 | Skip tour with first-time hints still enabled | No orientation; relevant opted-in contextual hint may appear; copy/settings clearly distinguish these choices |
| TR-11 | Existing/boosted vault not opted in | No automatic new hint burst; Help can explicitly explain/replay a mechanic |
| TR-12 | Reset hints or replay one mechanic | Scope matches command table; unrelated lessons, whole-tour choice and rewards preserved |
| UI-01 | Keyboard/touch user, no drag interaction | Continue, Skip, Undo, Help and departure path usable; visible focus; no hover-only control |
| UI-02 | Narrow screen, reduced motion, absent/hidden anchor | No blocked confirmation or tiny cutout; fallback action usable; motion preference honored |

### Delivery batches and evidence

**Batch A — state and definitions:** deliver stable IDs, mappings, lazy migration and narrow reset
commands. Review against ST-01–03, SK-11–13 and TR-12. No backend reward/schema change is needed
solely for local lesson dismissal. Document any existing reward-reconciliation dependency separately.

**Batch B — Skip step:** deliver the independent teaching selector, secondary controls, inline Undo,
pending-claim affordance and visible claim errors. Review SK-01–14 and UI-01–02. Don't mark this batch
complete while skipped prerequisite actions still require rebuilding/redispatching to recover.

**Batch C — four shared mechanics:** resources, SPECIAL, housing and departure; wire the existing
entry paths, dedupe and arbitration. Review TR-01–08 plus resource mapping. Record which actual
entry surfaces were walked, not just that the authored registry has four rows.

**Batch D — later mechanics and preferences:** add the other six authored hints, opt-in/settings,
single-mechanic Help and reset controls. Review TR-09–12 and each mechanic's eligibility row.
Verify no first-time explanation replaces existing success/critical-notification surfacing.

For each batch record touched integration points, acceptance IDs verified, methods used, failing
or unverified IDs and remaining dependency blockers. Appropriate later validation includes pure
selector/state checks, component interactions, real-service reward/reconciliation regressions and
manual keyboard/touch walkthroughs. Timing/resource playtests still follow the full-vault plan.
Don't call the additions complete from static inspection, catalog equality or screenshot-only evidence.

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
