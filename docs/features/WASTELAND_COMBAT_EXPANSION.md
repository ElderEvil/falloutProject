# Wasteland encounters and active combat skills

Recorded 2026-10-18 from the maintainer's three-part idea. First playable skill trial: Arena.

## Direction

1. Bring expedition site mechanics back into the exploration loop: discovering a site should give a clear
   opportunity to enter, make room choices, fight or salvage, keep loot, and retreat when needed.
2. Make more map places actionable. A location need not contain enemies: unattended supplies can simply be
   searched. Later expand existing map points by location archetype; do not turn every place into a battle.
3. Give dwellers a manual combat skill determined by their equipped weapon's **type and subtype**.
   The maintainer selected **charge earned through combat** for the first trial. Stamina remains an optional
   future alternative, with no stamina stat or economy introduced in this slice.

## Initial implementation

### Expedition sites and salvage

The existing expedition engine and entry UI remain the source of truth. Red Rocket and Super Duper Mart are
already wired through exploration details and map site markers; they were not removed. On spatial journeys,
only sites near the travelled trail are offered. No active journey means no temporary expedition markers.
That visibility rule can make the feature seem absent; this slice does not remove fog/trail requirements.

Three new level-1 sites reuse the same entry, resolution, loot, outcome modal and replay guards:

| Site | Map coordinates (catalog grid) | Contents |
| --- | --- | --- |
| Abandoned Campsite | 18, 38 | 10–25 caps and junk |
| Roadside Supply Truck | 48, 42 | 20–35 caps and junk |
| Forgotten Shack | 81, 54 | 15–30 caps and junk |

Each has one search room, no enemies, no trap, no stat roll, and a guaranteed reward on explicit resolution.
Loot joins the exploration haul; the existing return/collection flow settles it into the vault.
Spatial journeys consume an offered encounter once; legacy journeys retain the existing seven-day site cooldown.
These are authored encounter markers, not a blanket conversion of ordinary world locations into loot containers.

### Arena skill trial

- Dwellers start at zero charge. Each second of resolved combat adds 20 charge to standing dwellers, capped at
  100: five seconds of combat fill the meter (three ticks on the current two-second Arena clock). Countdown, idle rooms and knocked-out fighters add none.
- The player can activate either dweller side in Duel/Brawl; Hunt exposes skills only for real dwellers.
  Training bots and creatures have no manual skill.
- Activation reserves all 100 charge immediately, preventing double-clicks/replays. The attack resolves on the
  next Arena tick. Charge earned during that tick starts the next meter.
- Ordinary attacks deal 10% of team power per second (half the previous rate), capped per target at 5% of maximum HP per second. Skills bypass that training damage cap.
- Single-target skills hit the weakest standing enemy; area attacks hit every standing enemy. Ordinary round
  damage is calculated before skills, preserving the existing simultaneous retaliation rule.
- Charge and pending attacks persist in Arena state under the same room row lock as selection/start/ticks.
  Match reset, interrupted selection and completion clear them. API ownership and participant checks apply.
- The UI keeps the charge meter and skill button inside each fighter card; descriptions are available on hover or focus. Bench and journal are collapsed by default, and setup selectors hide during a live fight. Countdown, ready, impact and finish sounds use the existing audio manager. Hit reactions, queued-skill glow and a skill-burst banner respect reduced motion. Attacks appear in
  the battle journal. Existing nonlethal knockouts, XP, happiness and result banners settle in the normal round.

| Weapon | Skill | Bonus damage |
| --- | --- | --- |
| Unarmed | Haymaker | 2× combat power, single target |
| Melee / blunt | Crushing Blow | 2.5×, single target |
| Melee / edged | Cleave | 1.5× per enemy |
| Melee / pointed | Piercing Strike | 3×, single target |
| Gun / pistol | Quick Draw | 2.5×, single target |
| Gun / rifle | Aimed Shot | 3×, single target |
| Gun / shotgun | Scattershot | 1.5× per enemy |
| Energy / pistol | Overcharge | 3×, single target |
| Energy / rifle | Beam Sweep | 1.5× per enemy |
| Heavy / automatic | Full Auto | 3×, single target |
| Heavy / flamer | Firestorm | 1.5× per enemy |
| Heavy / explosive | Blast Wave | 2× per enemy |

These are prototype balance values. Effects use Arena combat power so equipment and existing combat modifiers
stay relevant. No skill effects have been enabled in incidents, quests or expedition combat.

## Next passes

- Playtest expedition discovery from a fresh spatial journey and improve encounter visibility if players miss
  the entry opportunity. Preserve reconnect, retreat, supply use and reward surfacing.
- Give existing world-location archetypes explicit search/fight/choice actions through their current dispatch
  and settlement services, with discovery requirements and replay protection. Do not pay loot from client state.
- Playtest short and long Arena matches, both team sizes, Hunt and simultaneous activations. Check whether
  five-second charge leaves enough opportunities to use a skill before a knockout; tune charge and damage together.
- Decide whether later effects need player-selected targets, stun/bleed/defence or enemy AI skill usage.
  Add those only after the damage-only trial is useful. Decide how asynchronous expedition combat will expose
  player timing before extending skills beyond Arena.

## Local trial

Apply the new Arena migration through the usual backend startup/migration flow. Assign adults to Arena,
select Duel/Brawl/Hunt and start. Surviving five seconds of combat fills a meter; activate a skill and observe the
next tick and journal. Reset the selection to clear the meters. Equip different weapon types/subtypes before
starting another match to compare their skills.

For salvage, send a level-1-or-higher explorer whose trail passes near a new site, then open its expedition
site picker or map marker. Search once, verify the outcome and retained haul, then verify repeat entry is blocked.
The existing `fo-cli expedition-scenario` helper can provision a legacy QA journey to expose the full site catalog.

## Playtest iteration (2026-10-18)

The maintainer reported overloaded UI and knockouts before a skill could charge. Ordinary Arena damage is now
halved, with a training damage cap, and charge fills after five seconds of combat. No tests are being added or
updated for this iteration at the maintainer's request; settle the mechanics through hands-on play first, then
update the existing timing/visibility expectations and add coverage for the chosen behavior.
