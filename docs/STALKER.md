# Easter Eggs — the Quiet Zone (a STALKER homage)

Design record for the game's cross-franchise easter-egg group. This file is the
single source of truth for **what this group is** and **the rules it must obey**.
The palette below is the concrete content to draw from when extending it.

---

## Essence

A **layered, ambiguous homage** — never a canon claim. Players should *recognize*
the inspiration (STALKER's Zone, Chernobyl), but the game must never assert that it
literally exists in Fallout.

The whole thing reduces to one sentence:

> There is an ugly, fenced, irradiated place somewhere in the wasteland. Some people
> claim it produces miracles. Most people who say that want to sell you something.

That reads at home in both Fallout's satire and STALKER's mystery.

## Hard rules (canon safety)

1. **"Anomalies" and "artifacts" are unverified local terminology.** They might be
   radiation effects, chemical contamination, odd pre-War industrial equipment, or
   scavenger exaggeration — never confirmed.
2. **No STALKER canon.** No named characters, factions, exact creatures, plot
   devices, or real artifact names. The Zone itself is never named as such.
3. **No reality-warping rewards.** Loot is curios, junk, decorative items, or
   ordinary irradiated salvage. Nothing proves the rumours true.
4. **Let NPCs disagree.** A believer calls it an anomaly; a scientist calls it a gas
   leak; a trader calls it a sales pitch. Contradiction is the point.
5. **Text-only for now.** No new mechanics, endpoints, or quests. If real item
   effects ever ship, keep them Fallout-shaped (rad resistance, carry, perception,
   crafting value) — not reality distortion.
6. **Progression-visibility red line still applies.** If any of this ever becomes a
   player-facing progression event, it must surface via modal/toast *in addition to*
   the notification bell.

## Shape (how it surfaces)

| Layer | Surface | Role |
|---|---|---|
| **Backbone** | `exclusion_zone` place group + one seeded location | the place always exists |
| **Atmosphere** | rare generated-bio rumours | hint at it, never confirm |
| **Discovery** | curated dweller `visited_places` (+ future exploration) | pins it on the map |

The discovery model:

- The location always exists in the seed registry.
- A curated dweller (or, later, an exploration discovery) can reveal it.
- Rare generated bios independently hint at it.
- Once found it is simply a dangerous-looking map location with flavourful lore.

Generated bios alone are a **weak primary route** — at a low chance a small player
population may never produce the rumour, and players do not read dossiers closely.
That is why the curated discovery route carries the weight.

---

## Implemented on this branch

- `backend/app/data/places/place_groups.json` — new `exclusion_zone` group,
  label **"Restricted Exclusion Site"** (`mdi:fence`, risk `high`).
- `backend/app/data/places/seed_places.json` — one seeded instance, **"The Quiet
  Zone"** (`kind: place`, `roles: ["visited"]`, `group: exclusion_zone`), with the
  fence/anomaly description.
- **Discovery route** — Moira Brown's `visited_places` (and a line in her bio) now
  include The Quiet Zone. Recruiting her registers the marker through the existing
  `map_service.register_bio_places` path.
- `backend/app/options/bios.py` — `ZONE_RUMORS` (8 ambiguous, first-person lines) and
  `maybe_zone_rumor(rng, chance)`.
- `backend/app/core/game_config.py` — `bio.zone_rumor_chance` (default `0.05`,
  env `BIO_ZONE_RUMOR_CHANCE`): the chance a procedurally generated dweller's bio
  carries one rumour. Rolled with the generation RNG, so `--seed` stays reproducible.

### Deliberately not done (yet)

- No exploration templates or discovery names (Phase 2) — event templates are
  placeholder-formatted and carry real regression risk.
- No curios/items (Phase 2).
- No terminals, radio fragments, or the fake wish-granter (Phase 3).
- **Vodka / Nuka-Cola "Non-Stop"** are *not* part of this branch. Vodka must **not**
  replace RadAway — that undercuts the joke and contradicts `GAME_MECHANICS.md`
  ("RadAway is the only cure"). Both belong to the separate consumables-behaviour
  work.

---

## Palette

### Location names

Primary: **The Quiet Zone** (shipped). Alternates:

- The No-Return Fence
- Reactor Valley
- The Singing Fields
- The Glass Orchard
- Sector Twelve
- The Ashen Perimeter
- The Red Forest Reserve
- The Dead Rail Yard
- The Stillworks
- The Black Rain Site

### "Anomaly" landmarks that stay plausibly mundane

Use as place descriptions or discovery names:

- **The Whistling Tunnel** — wind through damaged ventilation ducts sounds like voices.
- **The Glass Orchard** — trees coated in vitrified soil after an old blast.
- **The Magnetic Yard** — a scrap field that ruins compasses and attracts loose metal.
- **The Warm Puddle** — an irradiated geothermal runoff pool.
- **The Blue Flame** — leaking refinery gas that burns with an odd colour.
- **The Walking Shadow** — a billboard shadow that shifts with a broken rotating sign.
- **The Bent Road** — heat-warped pavement creates misleading distance illusions.
- **The Rain That Hurts** — an area known for especially nasty radstorms.

### A fake "wish granter"

A very STALKER-flavoured joke with no wish magic:

> Deep inside the site is a battered pre-War "Morale Optimization Terminal." Visitors
> insert a token, state a wish, and receive a corporate fortune such as: "Your request
> has been forwarded to management."

Results: "Wish denied: insufficient employee clearance." · "Congratulations! You have
been selected for mandatory optimism." · "A better future is just one approved
requisition form away." · "Please remain calm while your dream is processed."

### Bio rumour lines

The shipped eight live in `options/bios.py`. When adding more, keep them first-person,
secondhand, and deniable, and pair the supernatural claim with a mundane counterpoint:

> Claims to have seen a floating fireball in the Quiet Zone. Her former caravan
> partner says it was a leaking gas line and three bottles of vodka.

More seeds:

- "Won't travel near old reactors after sunset. Says the sky there turns red before a storm."
- "Insists that some ruins grow valuables the way forests grow mushrooms."
- "Says a masked guide led her through an exclusion fence, then vanished before accepting payment."
- "Refuses to explain the scar on his hand, only calling it 'the price of touching a miracle.'"
- "Swears there is a place where the ground hums and compasses point nowhere."
- "Has a map with one location repeatedly crossed out and rewritten as 'DON'T GO BACK.'"

### Exploration events

Keep the outcome small and avoid a new mechanical system:

- **The Bolt Test** — a corridor scattered with rusted bolts; throwing one ahead before
  each step changes nothing except that everyone feels safer.
- **The Shiny Thing** — a smooth, warm stone that glows until someone wipes the
  fluorescent paint off it. Reward: junk/curio.
- **The Detector** — a hand-built anomaly detector that clicks near radiation, wiring,
  canned food, and occasionally nothing at all. Reward: novelty scrap.
- **Campfire Expert** — a traveller explains how to survive the exclusion site: never
  travel alone, always carry bolts, and drink before entering. Only the first two
  sound sensible.
- **The Red Sky** — a radstorm turns the horizon crimson; one scout calls it an
  emission, another calls it weather, a third calls for shelter.

### Item and loot ideas

Player-facing text calls these **curios**, **oddities**, or **irradiated salvage**;
"artifact" is reserved for NPC superstition.

| Item | Description | Mechanical stance |
|---|---|---|
| Warm Pebble | A smooth stone that stays slightly warm. Probably radioactive. | Junk / low-value curio |
| Bent Bolt Bundle | Rusty bolts used by cautious scouts to test unstable ground. | Junk / crafting material |
| Cracked Pocket Detector | Clicks near radiation, loose wiring, and strong emotions. | Cosmetic / low-value |
| Black Glass Locket | Found near an old exclusion fence; no one agrees what is inside. | Collectible |
| Iridescent Slag | Beautiful, dangerous-looking industrial waste. | Sellable junk |
| Surveyor's Mask | An old respirator patched with tape and optimism. | Cosmetic apparel |
| Field Guide to Unsafe Places | Most pages missing; the surviving advice is "do not touch it." | Book / collectible |
| "Anomaly-Proof" Boots | Advertised as anomaly-proof; proven only puddle-resistant. | Low-tier apparel |
| Lead-Lined Flask | "For medicinal use," according to its previous owner. | Flavour item |

**Hard rule:** catalog-backed rows (`Weapon`/`Outfit`/`Junk`/generic `Item`) must be
built through `app/utils/item_factory.py` — a direct constructor call drops every
catalog-owned column and `test_item_factory_guard.py` fails the suite. Any new item
that can be granted as a reward must also be matched by `app/schemas/quest.py`'s
consumable-token list, or it is silently classified as junk.

### Radio, terminal, and ambient text

- **Garbled radio** — "...Survey team to base. The compass is wrong again. Repeat: the
  compass is wrong. Do not approach the—" *static*.
- **Pre-War safety bulletin** — "CIVIL DEFENSE NOTICE: Alcohol consumption does not
  reduce radiation exposure. Citizens spreading contrary information will be fined."
- **Campfire story** — "My cousin found a glowing stone in the Quiet Zone. Sold it for
  two hundred caps. His buyer died three days later." / "From the stone?" / "No, from
  arguing about the price with my cousin."
- **Tourist brochure** — "Visit the Exclusion Perimeter! Observe industrial progress
  from a government-approved safe distance." Found decades later with "SAFE DISTANCE"
  crossed out in marker.

### Vodka and Nuka-Cola jokes

Funny, but **not** mechanics:

- **Perimeter Vodka** — "A traditional cure for radiation, loneliness, and poor
  decision-making. Medical professionals dispute all three claims." Ordinary alcohol
  behaviour, humorous description, **no** radiation treatment.
- **Nuka-Cola Non-Stop!** — "Now with twice the fizz and none of the complicated
  questions." / "For the citizen who has nowhere safe to stop." Equal behaviour to an
  ordinary Nuka-Cola variant.

### A small narrative chain (no quest system)

1. A dweller bio mentions *The Quiet Zone*.
2. An exploration discovery reveals *The No-Return Fence*.
3. The player sees the actual seeded map marker.
4. The location description mentions a supposedly valuable "warm stone."
5. A later loot table very rarely produces an inert `warm_pebble` curio.

No quest log, no boss, no canon claims — just enough connected texture.

---

## Phasing

- **Phase 1 (this branch):** bio rumours + `exclusion_zone` group + "The Quiet Zone"
  seed + a guaranteed discovery route. ✅
- **Phase 2:** 1–2 tested exploration templates; several discovery names (e.g. "The
  No-Return Fence", "The Glass Orchard"); a few low-value curios.
- **Phase 3 (optional depth):** terminals, radio fragments, collectible survey notes,
  the fake wish-granting corporate terminal. Keep every explanation contradictory.
