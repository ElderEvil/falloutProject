# Living departures and reusable identities

Design contract for #831, following the maintainer's selection of a shared recruitment
pool retaining identity (2026-10-13). The model below is implemented: the canonical
lifecycle/availability state and its migration, exit settlement as a living departure, and
`DeparturePoolService.claim` for the shared pool. The pool is not yet player-reachable —
it has no endpoints or Trading Post UI, and read schemas do not carry departure labels.

## Player stories

- As an overseer granting an exit, I see “Left for the wasteland,” not a tombstone.
- As an overseer recruiting a former resident, I meet the same person, with their age,
  appearance, experience, and authored history intact.
- As a player creating private names or biographies, I choose whether that content can
  appear in another player's vault before a living departure becomes publicly recruitable.
- As an overseer remembering a permanent death, I keep the memorial even when generated
  artwork is later reused to create a different person.

## Canonical state and availability

Lifecycle is exactly one of `alive`, `dead_revivable`, `dead_permanent`, `wasteland`.
`wasteland` means a living unaffiliated person; it does not simulate an exploration journey.
Availability is exactly one of `vault`, `departure`, `pool`, `market`, `archive`.
Neither soft deletion nor a paid sale is a death. Room/job status remains separate.

| Lifecycle | Availability | Owner/membership | Allowed next transition |
|---|---|---|---|
| alive | vault | one active vault | temporary death, permanent death, departure, market |
| dead_revivable | vault | original vault, no active assignment | revival or expiry to permanent memorial |
| dead_permanent | archive | original vault memorial | no resurrection or same-identity recruitment |
| wasteland | departure | no active vault; previous vault retained as provenance | pool after eligibility and consent |
| wasteland | pool | no active vault; one shared pool entry | atomic claim into a new vault |
| alive | market | no active job; one existing paid listing | atomic purchase into a new vault |
| alive | archive | retired content, unavailable | eligible generated-content template copy |

A single dweller row is the membership authority. Store the previous vault separately;
never keep `vault_id` as both active ownership and seller/provenance. Database constraints
must prohibit pool+vault, market+pool, assigned+archive, and dead+pool combinations.
Death metadata exists only for actual deaths. Public queries exclude `departure` and
`archive`, and graveyard queries require `dead_permanent`, never a soft-delete flag.

## Transitions and existing mechanisms

Granting an exit goes through ExitRequestService and its existing vault-level advisory lock.
Keep despair thresholds, grace, one-ask-per-day, refusal cost, population restrictions,
and the action's toast. In one transaction detach the room, stop training/apprenticeship,
clear the pending request, update the vault cooldown, and record a living departure.
Do not call DeathService. Refuse departure while away on a quest/exploration or handling an
active response job; use the existing availability checks. Repeated grant cannot duplicate a
pool entry or reward. An exit releases capacity once and produces no caps or recruitment XP.

The person cannot be revived: they are alive. Historical notifications remain history;
new UI labels distinguish death from departure. A departure is visible in a separate history
filter, and must not inflate the active roster or the graveyard count.

Trading Post is the first shared-pool entry point. Reuse its offer UI, capacity/ownership
checks, price calculation, and transactional caps withdrawal. A living pool claim retains
identity and stats; it must not call the current recycling method with `reset_stats=True`.
Paid market listings remain a separate availability state. Radio keeps its current attraction
cadence and generated recruitment behavior in the first implementation. Connecting it to the
same pool is a follow-up; do not introduce a second claim mechanism or additional spawn rolls.

## Same person versus template copy

| Field | Living pool/market claim | Generated-content template reuse |
|---|---|---|
| ID and birth date | retain; never rejuvenate | new ID, normal spawn age |
| canonical name, portrait, visual identity | retain | copy only eligible generated content |
| level, XP, SPECIAL, max health | retain | ordinary rarity spawn rules, never dead donor stats |
| current health/radiation/happiness | retain; no free healing | ordinary new-person defaults |
| equipment, pets, consumables, loot | return to source vault transactionally | no copying possessions |
| room, job, training, pending requests | clear at departure/sale | no copying operational state |
| family/partner references | preserve privately; do not expose foreign-vault IDs | clear all identity relationships |
| bio entries and discovered places | retain safe authored history; no recipient map unlocks | generated origin/visited source only |
| source memorial | unaffected | immutable original memorial |

A pool claim must not grant creation, level-up, exploration, or duplicate template rewards.
Prior visited places are history, not automatic recipient fog-of-war unlocks. The same person
has one identity across the move; concurrent use of canonical curated templates must still
obey the existing target-vault template/name reservation checks.

DwellerRecyclingService currently restores the same soft-deleted row and optionally resets
stats/relationships. Reuse its CRUD row-lock primitive, not that restoration behavior for
permanently dead people. Template recycling must create a new row and reference the source
content privately, with no route back from memorial to alive. Only system-generated or
curated content is reusable; player-authored content is ineligible without explicit consent.

## Provenance, privacy, price and abuse policy

KISS/YAGNI decisions: one shared pool, the existing Trading Post price function, and no auctions,
player-set prices, global popularity score, simulation of exiled travel, or automatic radio integration.

- Preserve content provenance (`curated`, `generated`, `player_edited`) and sharing consent.
  System-authored text/art can be reused. Before sharing player-edited names/bios, offer an
  explicit confirmation describing cross-vault visibility. Opting out leaves the person in
  private departure history; it does not change them into a generated stranger.
- Existing rows with unknown provenance default to private departure, not public pool.
  Do not silently classify old edited content as generated. Show no previous account,
  vault name, chat history, user identifiers, or foreign-vault relationship links in offers.
- Reuse `trade_value`: rarity base 50/150/400 caps plus 10 caps per current level. The quote
  is checked again under lock; a mismatch returns a conflict without charging.
  The recruitment cost is a caps sink; departure pays the former owner nothing.
- Reuse the recycling eligibility delay of seven days before a public departure can be
  claimed. One person occupies one offer; no reroll or refresh endpoint creates extra stock.
  Keep the existing 20-offer market page limit; pagination/refresh cannot alter eligibility.
- A player/account cannot recruit its own departure, including through a second vault;
  retain source-account provenance privately for enforcement. Claims need target capacity,
  adequate funds, no active duplicate curated identity, and no conflicting availability.
- A pool claim or relisting cannot duplicate inventory, heal/reset the person, pay the old
  owner, or reset source provenance/cooldown. Ordinary paid market sales continue to have
  their existing single-sale guard; keep them distinct from free departures.

These are initial conservative design parameters using existing rules, not measured balance
results. Review the seven-day delay and price with production data after implementation.

## Migration and API compatibility

1. Add lifecycle/availability enums manually in Alembic; update PG_ENUM_LABELS_SNAPSHOT in
   the same commit. Add nullable provenance, sharing consent, previous membership and
   eligibility timestamps. No semantic zero/empty-string defaults.
2. Backfill before making canonical state required: genuine permanent deaths →
   dead_permanent/archive; revivable deaths → dead_revivable/vault; non-dead paid listings →
   alive/market; non-dead archived content → alive/archive; active rows → alive/vault.
3. Reclassify legacy EXILE rows only when EXILE is the recorded cause and the row matches
   the old permanent-death pattern: wasteland/departure, no active room, no death flags,
   no death cause or revival timer. Retain their prior vault as private provenance. Use the
   historic death timestamp as departure timestamp, but never infer sharing consent.
   An inconsistent EXILE row stays quarantined for review; a genuine later death must not
   be overwritten by a vague status match.
4. The backfill is idempotent: update only unclassified rows, and separate the name-keyed
   content provenance backfill from identity state. A rerun cannot reset membership,
   possessions, cooldowns, consent, or resurrect a person already processed later.
5. Convert equipment ownership and dangling jobs before enforcing constraints. Report
   unresolved rows and fail the constraint phase rather than inventing valid data.
6. Keep compatibility `is_dead`/`is_permanently_dead` derived from lifecycle,
   `is_deleted` from archive/unavailable membership, and `is_traded` from the existing sale
   settlement marker. Do not use these booleans as write authorities after cutover.
   Extend read schemas with canonical state and departure labels; existing status remains
   an activity compatibility projection. Unknown clients get a non-active departure
   representation, never `dead`. Update generated frontend types in the API change PR.
7. Data corrections have a documented no-op downgrade. Schema rollback cannot safely
   reproduce exile-as-death after people have been recruited; pause writes and restore a
   backup if operational rollback is needed.

## Regression and concurrency plan before implementation

Write failing tests for the current exile-tombstone bug before changing runtime code.
Use real SQLite sessions/factories for behavior tests and real PostgreSQL integration tests
for row locks and constraints; mocked CRUD cannot prove uniqueness.

| Contract | Required evidence |
|---|---|
| exit granted/refused | alive departure, single capacity release/cooldown, no death notification/revival, refusal unchanged |
| graveyard | genuine permanent deaths included; departures and market listings excluded; revivable window preserved |
| legacy migration | EXILE-only correction, unknown provenance private, genuine deaths intact, rerun no-op, inconsistent row rejection |
| claim | same ID/age/stats/health, no possessions or extra rewards, membership and caps commit together |
| two buyers | PostgreSQL concurrent sessions: exactly one succeeds/charges, loser gets conflict |
| claim versus relisting/death/delete | one canonical transition wins; no double ownership or poisoned session |
| ownership and privacy | foreign vault access denied; edited content opt-in; no source/account/chat disclosure; same-account claim denied |
| templates | new identity, source memorial immutable, no custom content copying, existing curated uniqueness guard |
| insufficient funds/full target | no changed membership, inventory, caps or provenance |
| tick/raw AsyncSession | departed person excluded from work, drain/population/jobs; CRUD uses execute(), not exec() |
| progression/UI | specific departure/recruitment toast, compatibility projections, filter counts and accessible labels |

## Delivery slices

1. Canonical model, compatibility readers, EXILE migration and graveyard regression fix.
2. Living departure settlement and private history with inventory/job cleanup.
3. Consent/provenance, shared Trading Post pool and atomic identity-preserving claims.
4. Separate immutable memorial/template-copy correction. Coordinate archive behavior with
   #838 and roster filters with #829. Ghoulification stays outside this contract.

Each slice needs its listed regression and concurrency checks before its feature is enabled.
The implemented slices are the canonical state, exit settlement and pool claims; the pool
becomes player-reachable once its endpoints, Trading Post UI and read-schema labels land.
