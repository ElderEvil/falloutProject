# Vault Diplomacy — war, peace and the screen that replaces the Trading Post

Owner: maintainer. Status: **proposal** (no scheduled work; opens as an issue before Slice 1).
Related: `docs/WORLD_MAP_PLAN.md` (Phase B raids, parked), `docs/plans/2026-11-27-map-multiplayer-slice.md`
(binding D1: exhibition duels, no loot), `docs/features/PLAYER_CONNECTIONS.md` (branch-only DMs).

## What this is

Replace the Trading Post screen with an **Envoy Terminal**: the single surface where two vaults that
have found each other on the atlas move from a radio handshake to a filed treaty — or to open war with
real costs. Mechanics are lifted from Amplitude's 4X diplomacy (Endless Space 2, Endless Legend,
Humankind) and cut down to what an asynchronous, single-vault, tick-driven game can actually honour.

Messaging is not the feature. Every status change is a structured filing with terms, a recipient, an
expiry and a price. Free text is a later, optional layer.

## What Amplitude actually does (measured, not remembered)

| Game | States | War entry | War exit | Currency |
|---|---|---|---|---|
| Endless Space 2 | Cold War (default on meeting), War, Peace, Alliance; **Truce** is a deal available only during War | Deal, only from Cold War | Truce deal during War; Peace only from Cold War | Influence |
| Endless Legend | War, Cold War (default on meeting), Peace, Alliance; **Truce** = temporary, 20 turns, then auto-drops to Cold War | Declaration; attacking armies inside a region you control is an automatic war | Truce only (or annihilation); breaking a Truce/Peace costs extra Influence; war price is greatly increased during a Truce | Influence |
| Humankind | Unknown, Peace, War, Alliance, Vassalage | **Formal War ≥80 War Support** or a refused Demand; **Surprise War ≥20**, −2 WS/turn and a Traitor badge that sours every other empire's attitude | White Peace; surrender at war support 0; forcing it drains the loser | Money, Grievances, Leverage (expansion) |

Facts worth stealing:

- **Cold War is the honest default.** Both Endless games drop you into it on first contact: hostile acts
  short of war are legal, and full peace is something you buy. Peace is a *treaty*, not the absence of war.
- **Peace is priced; war is priced too.** EL: every treaty term costs Influence paid by the proposer; the
  cost of treaties varies with standing, resource terms cost a flat fee regardless of size, and Declarations
  (Close Borders, Declaration of War, Inflation at −50% trade income) are one-sided and un-negotiable.
- **The negotiation screen shows acceptance before you send.** EL's "Contract terms" gauge previews the
  AI verdict and how each term moves it; refusals cost the relationship, counters are encouraged.
- **Humankind makes war a resource war.** War Support 0–100 with a peacetime equilibrium of 50, +2/turn
  rising to it and −1/turn falling. A signed treaty lowers the equilibrium by 5; an alliance by 20–30, so
  a real alliance makes war structurally hard. Grievances grant one-off +5 WS and expire in 10 turns;
  an unsettled Demand **suspends trade**; refusing a demand hands the other side +5 WS per demand and the
  choice of demanding war. War support below zero while refusing surrender stacks −10% stability, money,
  industry and food per turn.
- **Truces are a cooldown with a price tag.** EL's 20-turn truce blocks attacks, forbids proposing peace or
  alliance, and *raises* the cost of re-declaring war. That single rule is the entire anti-war-spam system.
- **Attitude is separate from status.** EL runs four axes (Envy, Fear, Trust, War), five levels each, and the
  strongest one is what's displayed. The War axis (Exhausted → Triumphant) sets what the loser must pay for a
  truce — a Triumphant empire demands tribute, an Exhausted one gives in.
- **Declarations and proposals are different animals.** ES2: a Declaration (war, close borders, downgrade) is
  unilateral and instant, while a Proposal sits until answered and Influence is charged only on acceptance.
  Humankind goes further and charges nothing to sign a treaty at all — the entire price is the war-support
  equilibrium drop and the attitude hit.
- **What players hate:** AI signing a treaty and breaking it next turn (ES2), diplomacy irrelevant to war
  (both), and worthless resource-swap spam farming diplomatic points (EL, fixed by ELCP ruleset).

## What transfers, what does not

**Transfers:** tiered statuses; a paid proposal with counter-offer and expiry; per-pair standing that prices
treaties; one-sided declarations; casus belli; war fatigue forcing peace; embargo as the "soft war" that
already has an implementation here (the Trading Post).

**Does not transfer:** territory capture, city cession, vassalage, fleet vision, research agreements, map
sharing (everyone already shares the atlas), third-party war declarations (world events cover that),
Leverage, reputation badges.

**Structural mismatch, stated plainly:** 4X diplomacy is turn-based and synchronous — a proposal lives one
turn. Here a player may be offline for two days, so every filing needs an **expiry** (48 h) and every lockout
needs wall-clock hours, not turns. The tick already runs daily; a "diplomatic day" is 24 h.

## Adaptation — Fallout flavour, same bones

The screen is the **ENVOY TERMINAL** (`/vault/:id/envoy`), subtitle *Inter-vault relations and overland
filings*. Nav entry replaces Trading Post. Furniture: teletype printouts, a holotape log, and `FILED`,
`VOID`, `EXPIRED` stamps. Copy is Vault-Tec bureaucracy meeting wasteland pragmatism; the broker is a
caravan company, not a government.

### Status ladder (per pair, unordered)

| Status | Amplitude ancestor | Fallout name | What it permits |
|---|---|---|---|
| `UNMET` | Unknown | **NO SIGNAL** | nothing; vault appears on the atlas identity-only |
| `CONTACT` | Cold War | **STANDOFF** | hailing, filings, duels as exhibitions, embargo. No trade, no raids |
| `CEASEFIRE` | Truce | **CEASEFIRE** (7 days) | nothing but talking; both sides locked out of hostile acts; drops to STANDOFF when it lapses |
| `ACCORD` | Peace | **ACCORD** | trade legal, exhibitions only, no war without breaking the accord |
| `COMPACT` | Alliance | **MUTUAL AID COMPACT** | accord rights + joint world-event progress + intel log |
| `WAR` | War | **OPEN HOSTILITIES** | stake duels, raids (Slice 4), war upkeep, no trade |

`EMBARGO` is a **modifier**, not a status: blocks trade while STANDOFF or ACCORD stands. It is the modern
descendant of EL's Close Borders and Humankind's demand-embargo, and it is the first consequence a player
feels because the Trading Post is the thing being replaced.

### Standing (replaces four attitude axes)

One integer per pair, −100…+100, labelled with Fallout: New Vegas' reputation ladder:
`VILIFIED · HATED · SHUNNED · NEUTRAL · ACCEPTED · LIKED · IDOLIZED`.

Deliberate simplification: EL's Envy/Fear/Trust/War axes are four hidden numbers players cannot reason about.
One visible number that prices treaties is worth more than four they cannot see. Deltas are transactional:

| Event | Δ Standing |
|---|---|
| Hail answered / proposal accepted | +5 |
| Trade completed under ACCORD | +1 |
| Accord signed / Compact signed | +15 / +30 |
| Embargo placed on you | −10 |
| Unjust declaration of war | −15 **with every met vault** (Humankind's Traitor badge) |
| Treaty broken by declaring war | −40, and Compact members see it |
| Grievance expired unaddressed | −5 |

### Findings the map produces

Three stages, and they are the ones the requester asked for:

1. **SIGNAL** — the atlas already shows every live vault's number, owner and coordinates, identity-only. That
   is a radio signal, not a relationship; no standing exists yet.
2. **CONTACT** — hailing requires *proximity*: one of your dwellers must have visited a location whose map
   point lies within `CONTACT_RADIUS` of their slot, or you must have been hailed first. This is the only new
   map rule, it uses coordinates already on the wire, and it makes "finding each other" a real act instead of
   a click on a marker that was always visible.
3. **FILINGS** — everything after contact is a filing with terms.

---

## The mechanics, with numbers

Costs are caps only. **No second currency** — Influence does double duty in 4X because it also paints borders;
here a new wallet would be a subsystem bought for one screen. Anti-spam is done by locks and expiry instead,
which the tick already understands. Prices sit in the existing economy band (settlement fee 150, city fee 300,
market dweller 50–400, loot 25–70, boosted start 15 000).

### Filings (one active per pair per direction)

| Filing | From status | Cost (caps) | Terms | Lapse |
|---|---|---|---|---|
| **HAIL** | UNMET→ | 0 | none | 48 h |
| **CEASEFIRE** | WAR | 200 | optional caps reparations | 48 h; runs 7 days |
| **ACCORD** | STANDOFF | 300 | trade clauses, optional cap transfer | 48 h |
| **COMPACT** | ACCORD | 1 500 | joint-operation clause | 48 h |
| **DEMAND** | STANDOFF/ACCORD, live grievance | 100 | reparations in caps or a labour contract | 72 h |
| **EMBARGO** | STANDOFF/ACCORD | 150 | one-sided, un-negotiable (EL Declaration) | until lifted |
| **DECLARATION OF HOSTILITIES** | STANDOFF/ACCORD | 400 with a grievance, **1 200 without** | none | immediate |

Rules that make refusal mean something (Humankind's, translated):

- Refusing a DEMAND costs the refuser −10 standing and grants the demander a **casus belli**: war is then
  legal at the grievance price for 7 days.
- Refusing a filing locks that filing kind for 24 h and raises its next price ×2. Repropose freely after 72 h.
- A CEASEFIRE lapses → STANDOFF, never straight to WAR. Re-declaring inside the ceasefire costs ×3 and
  forfeits the grievance discount — EL's truce rule, and the actual reason war spam does not happen.
- Breaking an ACCORD or COMPACT by declaring war is legal, priced at ×3, and costs −40 standing. An oath
  is not a shield; it is a receipt.
- **Counter-offers are one click, never a term sheet.** Accepting, refusing, or accepting *if* N caps are
  added to the terms. EL's negotiation panel previews every term against an acceptance gauge; that works
  across one turn and is unusable across 48 hours. Humankind collapsed counters to a single game-priced
  money sum precisely so the whole exchange is one click — with hours between replies that is the only shape
  that survives latency.

### Standing treaties cost every day

A treaty paid once and forgotten is decoration. ES2 charges per-turn Influence upkeep on agreements and
auto-cancels them when a side cannot pay — a lapse rule that costs no UI. Copy it: **ACCORD 25 caps/day,
COMPACT 75 caps/day**, deducted in the existing resource pass, and after 48 h of arrears the filing voids to
STANDOFF with −10 standing to the payer. This is the only thing that makes a long peace a commitment rather
than a switch, and it gives the tick a reason to touch the diplomacy table at all.

### War has to bite — four consequences, cheapest first

1. **Trade dies (Slice 2, mandatory).** Cross-vault purchases from the market require ACCORD. At WAR an
   automatic EMBARGO applies both ways. This is the consequence every player notices within a day because
   the Trading Post is gone and its replacement visibly closes.
2. **Stake duels (Slice 2).** Exhibition duels stay zero-stakes (binding D1). At WAR the same `PvpDuel`
   row becomes live-fire: both sides escrow caps (1% of vault caps, floor 100, ceiling 2 000) and the loser
   pays the winner. Snapshots are already frozen before settlement, so no live vault is read.
3. **War upkeep (Slice 2).** Each 24 h at WAR drains `40 × vault level` caps from each belligerent, settled in
   the existing resource pass. Refusing a surrender or ceasefire offer adds −10% caps income, stacking to
   −50% — Humankind's punishment shape, applied to the one economy this game has.
4. **Raids (Slice 4, parked Phase B).** The only state in which a looting raid is legal. Reuses the parked
   `RaidTarget` contract verbatim: versioned minimal defender snapshot, idempotent state machine, loot caps
   and one stamped item. No live-vault reads, ever.

### War ends

`war_started_at` plus accumulated battle results give a **War Fatigue** clock. Fatigue never ends a war by fiat:

- Day 7: both sides see fatigue; a CEASEFIRE filing costs 0 instead of 200.
- Every 7 days past that: war upkeep rises +25% and the refused-ceasefire income penalty deepens by another 10%.
- Day 21: the tick files a **CARAVAN ARBITRATION** offer — a 7-day ceasefire with the terms pre-filled at current standing — as an ordinary filing either side may accept, refuse or ignore. Refusing costs −15 standing; it does not get overruled.

Amplitude's own post-mortem on this is worth obeying: Endless Space 2's **forced** Truce (imposed at 80%/20% war momentum as an anti-snowball rule) is one of the most disliked mechanics in the game, and Humankind's pre-Achilles war support was treated as hit points, which produced wars that ended while the player was winning. The fix in both cases was the same — make losing *cost* rather than stop. A player who is behind should be choosing between compounding upkeep and accepting terms, never handed a ceasefire. So: fatigue prices peace, it does not impose it.

Surrender is a settlement, not a screen: the losing side files a DEMAND-shaped surrender (caps reparations,
one labour contract, territory-free) and the winner accepts or keeps fighting at escalating upkeep. With no
territory to cede, this is as close to Humankind's surrender terms as the game's model honestly allows —
and it closes the seam Amplitude left open. Humankind has **no negotiated peace at all**: only White Peace
or total surrender, criticised by players because mid-war there is no "settle at current lines" option.
Here every filing already carries terms and an expiry, so a mid-war settlement costs nothing extra to support.

### What peace pays (or nobody signs)

- **ACCORD:** the market reopens (dweller labour contracts, priced as today), +1 standing per completed deal,
  and the caravan trade clause — one settlement fee waived per day per pair. Against 25 caps/day upkeep, the
  break-even is roughly two completed purchases a day: a quiet accord bleeds caps, a busy one earns them.
- **COMPACT:** joint progress on world events (the same co-op plumbing already behind the `world_events` flag),
  shared intel entries in the Journal, and no stake duels between members.

### Four Amplitude failures designed out, on purpose

1. **No forced truce.** ES2 imposes one at war-momentum extremes and players hate it; here fatigue prices peace.
2. **No winner-pays-to-refuse.** ES2's other top complaint is that rejecting a peace offer costs Influence.
   Refusal here costs standing, never caps, and the refuser is never the one paying to say no.
3. **No term-sheet negotiation.** Counter-offers are one priced add-on, because 48-hour latency kills anything
   that requires reading a grid of mutually adjusted clauses.
4. **No free treaty spam.** ES2's agreements bill per turn; without that, cheap treaties farm goodwill for
   nothing. Upkeep plus a standing-cost per broken treaty is the whole defence.

---

## Delivery slices

Each slice ends with a playtest hypothesis, per the feature-intake gate.

### Slice 1 — the screen swap (no new statuses), ~350 prod / 250 test
- `VaultRelation` (pair key ordered by UUID, `status`, `standing`, `met_at`, `locked_until`) and
  `DiplomaticFiling` (`kind`, `terms` JSONB, `from_vault`, `to_vault`, `status`, `expires_at`, `responded_at`).
  Two tables; grievances are later filings of kind `GRIEVANCE`.
- Endpoints under `/vaults/{vault_id}/envoy`: `GET /signals`, `POST /hail`, `POST /filings`,
  `POST /filings/{id}/respond`, `GET /log`, and `GET /config` (the effective knobs, so the UI never
  contradicts the server).
- `DiplomacyConfig` in `game_config` with the defaults in the tuning table, trade gate shipped at `standoff`.
- Frontend `modules/envoy/` replaces `modules/trading/` route entry; `TradingPostPanel` moves into the Envoy
  Terminal's ACCORD tab (the market survives; its front door changes). Fallout copy throughout.
- Proximity gate for HAIL, using coordinates and visited locations already in the map read.
- Notifications: `DIPLOMACY_HAIL`, `DIPLOMACY_FILING_ANSWERED` (bell + toast — progression-visibility red line
  applies to an accepted filing). Enum cost is the usual four registrations.
- Flag `vault_diplomacy`, default off; owner = maintainer, decision at the first playtest.
- **Hypothesis:** strangers hail each other and answer within a day, at a rate that makes the filing lock
  feel like scarcity rather than friction.

### Slice 2 — statuses with teeth, ~600 prod / 450 test
- ACCORD, EMBARGO, WAR: trade gating, stake duels, war upkeep, breaking costs, standing deltas.
- Standing treaty **upkeep** (25/day accord, 75/day compact) with arrears auto-void — the one tick change.
- Ceasefire lifecycle and the War Fatigue clock; no forced ceasefire anywhere in the code path.
- **Hypothesis:** at least one war per ten vault pairs, and wars end by ceasefire rather than abandonment,
  with trade loss visible in caps/day.

### Slice 3 — casus belli, ~350 prod / 250 test
- Auto-generated grievances from real events (stake duel initiated against you, embargo placed, compact
  partner attacked, filing refused), 7-day decay, DEMAND with reparations, unjust-war global standing hit.
- One **structural** grievance worth including because it is free: adjacent vault slots generate a slow
  "overlapping claims" grievance on a timer. Most of Humankind's grievance catalogue is proximity- and
  ideology-driven rather than event-driven, which is why its map feels politically alive without anyone
  doing anything.
- **Hypothesis:** declarations split roughly 70/30 justified vs unjust, and unjust wars visibly cost
  reputation with third parties.

### Slice 4 — raids, ~900 prod / 700 test (parked Phase B revival)
- Loot-bearing raids legal only at WAR, reusing the parked `RaidTarget` contract; loot caps + one item.
- **Hypothesis:** raiding changes a war's outcome more than duels do, without either side feeling robbed
  while offline.

**Not in scope, deliberately:** free-text envoy messages (the `feat/player-connections` branch stays parked),
vassalage, territory, third-party war pacts, alliance chains, diplomatic victory.

---

## Open decisions for the owner

1. **Trade gating — resolved as a knob, not a decision.** See the tuning surface below. It ships at
   `standoff` (market stays open), flips to `accord` for the second playtest week with a one-line deploy.
2. **Caps or a second wallet:** recommendation is caps with locks. Say so now if you want "Influence" as a
   generated resource, because that is a subsystem, not a config value.
3. **Proximity radius** for HAIL (in map units) and whether being hailed ever waives it. Recommendation:
   waive in one direction — you may always answer someone who reached you.
4. **War upkeep on vaults with fewer caps than the drain:** allow caps to floor at 0 and apply the −10%
   production penalty instead (recommended), or auto-file a ceasefire. Never delete dwellers for war debt.

---

## Tuning surface — every number above is a config value

The repo already has the right idiom: `GameConfig` is a tree of `BaseSettings` sub-models with an env prefix,
so a balance change is an env var and a rolling restart, not a commit (`INCIDENT_SPAWN_CHANCE`, `GAME_LOOP_*`
and friends). Diplomacy follows it exactly — `DiplomacyConfig(BaseSettings, env_prefix="DIPLOMACY_")`, composed
into `GameConfig`, seeded with the defaults below.

Three deliberate choices in the shape:

- **The trade gate is a `Literal["standoff","accord","compact"]`, not an enum.** A new enum costs the usual
  registration sweep; a validated literal is free and env-friendly.
- **It is not a `FeatureConfig` flag.** `vault_diplomacy` is the dark-ship flag with an owner and a date; the
  gate is a policy that outlives the flag and gets tuned forever. Flags get deleted, knobs do not.
- **The client reads effective values from `GET /envoy/config`** and renders the rule from them, so the UI can
  never claim a market that the server has closed.

| Env var | Default | What it moves | What the playtest watches |
|---|---|---|---|
| `DIPLOMACY_TRADE_GATE` | `standoff` | which status unlocks cross-vault purchases | market volume before/after the flip |
| `DIPLOMACY_HAIL_RADIUS` | `2.0` | map units a dweller must have visited near their slot | how often hails are even offered |
| `DIPLOMACY_FILING_TTL_HOURS` | `48` | how long a filing waits for an answer | unanswered-filing rate |
| `DIPLOMACY_REFUSAL_LOCK_HOURS` | `24` | lock after a refusal | repeat-offer spam |
| `DIPLOMACY_REPROPOSE_HOURS` | `72` | when a refused filing is free again | grudges vs. persistence |
| `DIPLOMACY_CEASEFIRE_DAYS` | `7` | ceasefire length before it lapses to standoff | wars that re-ignite on lapse |
| `DIPLOMACY_WAR_UPKEEP_PER_LEVEL` | `40` | daily caps drained per belligerent | caps lost per war-day |
| `DIPLOMACY_FOOTING_PENALTY_PCT` | `10` | income penalty per refused ceasefire | whether wars actually end |
| `DIPLOMACY_FATIGUE_START_DAYS` | `7` | when a ceasefire becomes free | median war length |
| `DIPLOMACY_FATIGUE_RAMP_DAYS` | `7` | steepness of the upkeep ramp | — |
| `DIPLOMACY_ARBITRATION_DAY` | `21` | when the broker files an offer | refused-arbitration count |
| `DIPLOMACY_ACCORD_UPKEEP` / `_COMPACT_UPKEEP` | `25` / `75` | daily cost of standing treaties | arrears voids per week |
| `DIPLOMACY_UNJUST_WAR_MULTIPLIER` | `3` | surcharge on a war with no grievance | justified/unjust split |
| `DIPLOMACY_STAKE_PCT` / `_MIN` / `_MAX` | `1` / `100` / `2000` | stake duel escrow | duel stakes vs. caps on hand |

**Playtest sequencing, not an A/B split.** The player base is too small to split — two cohorts give two
unreadable numbers. Run it in time: week one at `standoff` measures whether anyone hails and files at all;
week two at `accord` measures what closing the market costs in trade and whether accord adoption responds.
One env change between weeks, no code, and the comparison is honest because the population barely moves.
That also settles the gate question with evidence instead of taste — which is the whole point of it being a
setting rather than a decision I make for you.
