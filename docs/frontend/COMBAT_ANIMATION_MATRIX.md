# Combat animation matrix

Status: catalog-audited design; skill icons and the first shared motion slice implemented on 2026-10-25.
Spec reference: [#1140 — weapon-type skill icons and free combat animation assets](https://github.com/ElderEvil/falloutProject/issues/1140).
Playback foundation: [shared combat playback](../features/WASTELAND_COMBAT_EXPANSION.md#shared-combat-playback-2026-10-25).
Animation source research: [dweller rig and animation sources](../features/DWELLER_RIG_ANIMATION.md).

The matrix covers the actual weapon catalog and dweller races. It describes reusable choreography, rather
than a separate animation asset for every item/race combination. Combat rules, damage, targeting and turn
order remain server-owned. Arena skills are extra attacks before the normal hit; incidents use normal attacks only.

## Audited coverage

- **136 catalog weapons**, across all **11** `(weapon_type, weapon_subtype)` pairs in the skill registry,
  plus the unarmed fallback.
- **Four dweller races:** human, ghoul, super mutant and synth. Their existing states are listed below.
- **Power armor is the only outfit modifier.** All 17 catalog entries with `outfit_type = power_armor` use
  one common armor treatment. Other outfits and their rarity do not change animation behavior.
- Weapon variants inherit their family presentation. Use the existing
  [`family_key()`](../../backend/app/utils/weapon_naming.py) normalization, followed by a small set of explicit
  family overrides where the generic motion/effect would misrepresent the weapon.

Sources: [weapon catalog](../../backend/app/data/items/weapons.json),
[skill registry](../../backend/app/services/combat/weapon_skill.py),
[race/state enums](../../backend/app/core/enums.py), [race presentation policy](../../backend/app/options/races.py),
and [power armor catalog](../../backend/app/data/items/outfits/power_armor.json).

## Weapon and skill matrix

The icon portion uses standard Lucide icons from the existing `@lucide/vue` dependency. Their canonical key lives with
weapon-skill metadata and is consumed by meters, preview, tooltips and journal.
Both type and subtype matter: an energy pistol must not inherit the ballistic-pistol icon just because both
have subtype `pistol`. Existing item icons in `frontend/src/core/models/items.ts` are useful precedents.

| Type / subtype | Items | Catalog examples | Normal attack presentation | Existing Arena skill | Icon concept |
| --- | ---: | --- | --- | --- | --- |
| Unarmed | — | No equipped weapon | Short forward punch; contact flash | Haymaker, single target | Fist |
| Melee / blunt | 5 | Baseball bat, Pickaxe, Pool cue, Fire hydrant bat, Power fist | Weighted strike; family exceptions below | Crushing Blow, single target | Hammer / impact |
| Melee / edged | 12 | Butcher knife, Relentless raider sword, Ripper, Grognak's axe | Slash with a visible edge arc | Cleave, area | Sweeping blade |
| Melee / pointed | 1 | Kitchen knife | Short straight thrust; concentrated contact | Piercing Strike, single target | Point / thrust |
| Gun / pistol | 26 | Pipe pistol, .32 pistol, 10mm pistol, Scoped .44, T60 pistol | Brief preparation, one muzzle pulse and recoil | Quick Draw, single target | Pistol |
| Gun / rifle | 35 | Assault rifle, BB gun, Hunting rifle, Sniper rifle, BOS assault rifle | Braced shot with restrained body recoil | Aimed Shot, single target | Rifle / sight |
| Gun / shotgun | 12 | Combat shotgun, Sawed-off shotgun, Shotgun | Wide muzzle flash and stronger recoil; one normal target | Scattershot, area | Pellet fan |
| Energy / pistol | 17 | Alien blaster, Laser pistol, Plasma pistol, Assaultron head, Institute pistol | Compact energy discharge; family-specific trail | Overcharge, single target | Charged orb |
| Energy / rifle | 11 | Laser musket, Alien disintegrator, Laser rifle, Plasma rifle, Pulse rifle | Braced energy discharge; family-specific trail | Beam Sweep, area | Beam / energy sight |
| Heavy / automatic | 7 | Gatling laser, .50 cal machine gun, Ultracite Gatling laser | Short sustained burst and repeated restrained recoil | Full Auto, single target | Burst / rotating barrel |
| Heavy / flamer | 5 | Flamer and its variants | Braced stance and short flame stream | Firestorm, area | Flame |
| Heavy / explosive | 5 | Fat Man, Missile launcher, Junk Jet | Launch motion, projectile, then family-appropriate impact | Blast Wave, area | Launch / burst |

Area visuals affect only the targets supplied by the resolved action. Ordinary shotgun, automatic and
explosive-family attacks must not visually imply extra targets or damage. Multiple cosmetic pellets/bullets
still share the action's authoritative impact; they do not generate additional HP changes.

## Race × weapon motion matrix

These are proposed body-motion variations of the weapon presentation above. They change pose, motion
amplitude and recovery shape within the same action window; they do not change attack order or cadence.
The synth column describes visible Gen I/II synths; Gen III and unknown synth generations use the human column.
The ghoul column is the sane baseline; wild/feral adjustments follow in the state table.

| Weapon action | Human | Ghoul | Super mutant | Synth, Gen I/II |
| --- | --- | --- | --- | --- |
| Unarmed | Compact jab and reset | Forward-leaning jab | Broad, heavy punch | Direct thrust; precise reset |
| Blunt | Swing, contact, follow-through | Guarded swing with shorter follow-through | Large shoulder-led strike | Measured swing and controlled stop |
| Edged | Clear slash arc | Compact close slash | Broad sweeping slash | Clean, controlled slash |
| Pointed | Forward thrust and withdraw | Close, forward-leaning thrust | Heavy short thrust | Straight, precise thrust |
| Pistol | Snap preparation and small recoil | Guarded preparation and recoil | Firm grip; less body displacement | Crisp preparation and controlled recoil |
| Rifle | Shoulder brace and recoil | Forward brace and compact recovery | Planted stance and restrained recoil | Stable brace and precise reset |
| Shotgun | Strong recoil and reset | Braced recoil and compact reset | Low visible displacement; weighted recovery | Controlled recoil and deliberate reset |
| Energy pistol | Brief charge pose and release | Guarded charge and release | Firm stance and short release motion | Precise charge and release |
| Energy rifle | Brace and discharge | Forward brace and discharge | Heavy, planted discharge | Steady discharge and exact reset |
| Heavy automatic | Sustained brace; repeated small recoil | Forward brace; compact repeated recoil | Planted stance; minimal body displacement | Stable brace; measured repeated recoil |
| Flamer | Planted lean; hold stream | Guarded lean; hold stream | Broad stance; hold stream | Controlled stance; hold stream |
| Launcher | Brace, launch recoil, settle | Forward brace, launch recoil, settle | Heavy brace and compact recoil | Deliberate launch and controlled settle |

## Existing race states

| Race | Existing state | Adjustment to the matrix |
| --- | --- | --- |
| Human | No state | Human baseline |
| Ghoul | `sane` | Deliberate weapon use; no automatic feral posture |
| Ghoul | `wild` | More uneven anticipation/recovery; retain the equipped weapon's delivery |
| Ghoul | `feral` | Hunched, abrupt motion; unarmed attacks can resemble a rake. An equipped gun still fires |
| Super mutant | `mild` | Large-body baseline |
| Super mutant | `average` | More shoulder weight in the same action window |
| Super mutant | `behemoth` | Largest sense of mass; keep displacement bounded so the actor and meters stay in view |
| Synth | `gen_1` | Clearly mechanical preparation and stop; subtle mechanical impact sparks |
| Synth | `gen_2` | Smoother mechanical motion and controlled recovery |
| Synth | `gen_3` or missing/unknown generation | Human motion and hit reaction; no automatic robot effects |

The Gen III fallback follows `passes_as_human()` in `options/races.py`. Current purposeful-action restrictions
for feral ghouls/behemoths concern intentional chat actions; they do not establish a combat equipment ban.
Animation must follow the actual equipped weapon and resolved action. Missing/unknown race uses human motion.
Use the established body-size helper; do not invent a parallel portrait-scale catalog. Adults and elders keep
their existing eligibility, with no animation-derived age penalty. Training bots and creatures are separate
actor types, not additional dweller races.

## Power armor modifier

Read the actual equipped outfit's `outfit_type`, not its name, rarity, portrait clothing or visual prompt.
Apply this once to any supported race and weapon; do not stack a second mass effect on top of a super mutant.

| Aspect | Without power armor | With `power_armor` |
| --- | --- | --- |
| Body motion | Race/state profile | Heavy planted stance; shorter body travel; weighted settling |
| Recoil | Weapon motion adjusted for body | Smaller displacement; firm recovery; weapon still visibly fires |
| Melee | Race/state follow-through | Weighted strike and controlled follow-through; preserve swing vs thrust vs punch |
| Receiving a hit | Race-appropriate flinch | Armor spark/flash and brief torso jolt; never an unreported block or immunity |
| Timing / mechanics | Existing action window and outcome | Same impact marker, targets, HP outcome and skill behavior |

Every non-power-armor outfit uses the normal race/state profile. Faction, gender, rarity, pets and cosmetic
clothing do not add animation behavior in this design.

## Item-family exceptions

These are proposed delivery/motion parameters reusing shared effects, not bespoke clips for every subtype.
Apply them to normalized families so variants inherit them. An override never changes the skill selected by
the current `(type, subtype)` registry, including its single-target/area behavior.

| Catalog family | Proposed exception | Existing skill stays |
| --- | --- | --- |
| Power fist | Armored punch, not a bat swing despite `melee/blunt` | Crushing Blow |
| Pool cue | Straight jab with shaft contact, not a broad bat swing | Crushing Blow |
| Pickaxe | Overhead chopping strike with concentrated contact | Crushing Blow |
| Ripper; Surgical Ripper | Short vibrating cut; shared wider sweep for the area skill | Cleave |
| Gatling laser; Ultracite Gatling laser | Energy burst trail instead of ballistic muzzle/tracer treatment | Full Auto |
| Plasma pistol; Plasma rifle | Energy orb/pulse; the area skill can use a fan of pulses rather than a continuous laser | Overcharge / Beam Sweep |
| Gauss pistol; Gauss rifle | Charged tracer and sharp physical impact | Quick Draw / Aimed Shot |
| Railway rifle | Visible spike/tracer and concentrated physical impact | Aimed Shot |
| Tranq gun | Small dart impact; no invented stun, sleep or status effect | Quick Draw |
| Assaultron head | Charged energy discharge; no human-head or creature attack substitution | Overcharge |
| Junk Jet | Debris projectile and debris fan for the area skill; no automatic fiery explosion | Blast Wave |
| Fat Man; Missile launcher | Arcing or direct launch respectively, followed by a burst on the supplied targets | Blast Wave |
| Alien blaster; Alien disintegrator; Pulse rifle | Short energy pulse variant of the shared energy effect | Overcharge / Beam Sweep |

All remaining families inherit the weapon matrix. Prefixes such as Rusty, Hardened, Enhanced, Focused,
Armor piercing and Recoil compensated do not create new animation sets. `Auto pipe pistol` can use a short
cosmetic burst while retaining its pistol skill and one damage application. `Bayoneted pipe rifle` still fires
in a normal rifle action. `Incendiary Institute pistol` does not imply burn damage or a damage-over-time effect.
`Ultracite Gatling laser` needs its explicit family entry because `family_key()` does not strip `Ultracite`.

## Scope and implementation gaps

For **#1140's first slice**, centralize icon selection for all 12 skill entries and reuse a small effect set.
The existing `strike`, `shot`, `beam`, `sweep`, `flame` and `blast` vocabulary is the starting point. A new
profile reuses those primitives where its delivery can remain honest. Race/state and power-armor
choreography share the same component; the issue does not require 48 bespoke race/weapon clips.

Implemented first motion slice:

- Resolved actions snapshot `actor_body` and each target's `body`, derived on the server from actual
  race/state and equipped outfit. Historical events default to human motion. Power armor overrides race
  weight; no other outfit changes motion. Gen III/unknown synth generations retain human presentation.
- `CombatantMotion.vue` is shared by Arena and incidents. Only portraits move: meters, skill controls
  and damage labels stay anchored. Melee winds up then follows through; ranged attacks brace and recoil.
  Metal targets add sparks at impact. Reduced motion and accelerated catch-up keep bodies stationary.
- Sane ghouls, wild/feral ghouls, mutants, behemoths and visible synths use bounded variations within the
  existing prepare/impact windows. Mild/average mutants share a profile; Gen I/II synths share one too.
- Family exceptions implemented: power fist punch, pool cue thrust, plasma/alien/pulse energy pulse,
  Gatling laser beam, and Junk Jet debris. Edged weapons slash, pointed weapons thrust, and shotgun/
  automatic weapons use a cosmetic burst with one authoritative HP impact. Other family refinements
  in the table above remain proposed.

Remaining artwork limits:

- Current character portraits are still images. Lean, recoil, launch cues, slashes and impact effects work
  with cutout motion. Visible arm/grip/aim changes need additional poses or separate artwork. The matrix
  describes choreography without assuming a new rig or animation runtime.
- Item-card images are not automatically usable as held weapons: the current resolver can return a stat
  card or generic pistol fallback. Verify the exact art before attaching it to a character or using a muzzle
  anchor; retain a neutral family effect when suitable art is unavailable.
- Skill glyphs use locally bundled Lucide components in `CombatSkillIcon.vue`, with no custom SVG path
  data or runtime icon downloads. Lucide's license is retained by the installed dependency. Standard
  action symbols distinguish skill categories where dedicated firearm silhouettes are unavailable:
  Quick Draw uses `FastForward`, Aimed Shot uses `Crosshair`, Scattershot uses `Expand`, Overcharge
  uses `Zap`, Beam Sweep uses `ScanLine`, and Full Auto uses `ChevronsRight`. Unarmed/melee/flamer/
  explosive skills use `HandFist`, `Hammer`, `Sword`, `MoveUpRight`, `Flame`, and `Bomb`.
  External animation assets require exact-source license checks under #1140; the selected skill hit
  asset is documented below.

## Asset shortlist researched 2026-10-25

The maintainer wants complete static **Shelter-style** Eyebot/Protectron images, replacing the current
incorrectly assembled poses. Robot animation, Fallout 3/4 renders and another parts assembly are outside
that request. Skill animations remain a separate selection. This is a shortlist, not imported game assets.

### Skill effects

The shared Arena and expedition playback uses two CC0 effects: Sinestesia's [Hit Animation 2](https://opengameart.org/content/hit-animation-2-frame-by-frame) for most skills (with an energy color variant), and Sinestesia's [Explosion Animations 2](https://opengameart.org/content/2d-explosion-animations-2-frame-by-frame) for Blast Wave. The source PNG frames were resized and converted to 16-frame, 128px-per-frame WebP strips in `frontend/public/assets/combat/`. Firestorm uses a CSS heat wave and Scattershot a radial pellet burst. Crushing Blow adds a shock ring and Full Auto uses tracer streaks. Skills share the existing arena skill sound. Effects display on each resolved target and use a still frame for reduced motion and accelerated playback; the original weapon-specific SVG feedback remains in place.

| Source | Publisher-listed license | Proposed use | Preparation / verification |
| --- | --- | --- | --- |
| [Cethiel — Weapon Slash](https://opengameart.org/content/weapon-slash-effect) | CC0 | Cleave; edged weapon follow-through | Downloaded and inspected the public archive: 125 PNGs. Frame widths vary (e.g. 124–126px with 150px height), so normalize canvas/anchors before making a sheet. The page advertises five effects and color variants. |
| [Sinestesia — Hit Animation 2](https://opengameart.org/content/hit-animation-2-frame-by-frame) | CC0 | Haymaker, Crushing Blow, Piercing Strike and gun impacts | Transparent 16-frame PNG atlas. Source frames are 1024px; export at the actual combat effect size. |
| [Sinestesia — Explosion Animations 2](https://opengameart.org/content/2d-explosion-animations-2-frame-by-frame) | CC0 | Blast Wave; explosive weapon impacts | Four transparent animations; 512px frames in 4096px atlases, with a half-size option. Select one and optimize it rather than shipping the 18.3MB source pack. Junk Jet retains debris presentation. |
| [Mikodrak — Burning Fire](https://opengameart.org/node/16403) | CC0 | Firestorm target flames; incident fire | Forty transparent PNG frames. It is a looping flame, not a ready directional flamethrower stream. |
| [SpritePilot — Combat](https://spritepilot.com/free-game-assets/combat), [Effects](https://spritepilot.com/free-game-assets/effects), [Magic](https://spritepilot.com/free-game-assets/magic) | CC0 on each publisher page | Quick Draw, Aimed Shot, Scattershot and Full Auto muzzle flashes; Overcharge/Beam Sweep energy orbs and bolts | Pages provide animated previews and 16/32px strips: muzzle flash 5 frames, laser bolt 6, energy orb 8. Pixel style needs an in-scene comparison. Direct archive access returned 403 during this research, so archive contents/licenses have not been independently inspected. |

CodeManu's [Free VFX Pack](https://codemanu.itch.io/vfx-free-pack) is a secondary lead: its description
says public domain/no credit, while its metadata says CC BY 4.0. Do not record it as verified CC0 without
resolving that discrepancy. Kenney's Particle Pack supplies textures, rather than finished animation clips.

Recommended first comparison: slash, hit and explosion at phone/desktop combat scale, preserving the
existing impact marker. Retiming a cosmetic burst must not add HP applications. Keep sprite effects below
meters/controls, mirror directional effects, and retain a static impact frame for reduced motion.

### Complete robot image references

| Robot | Source | Verified state |
| --- | --- | --- |
| Protectron | [Nukapedia file](https://fallout.fandom.com/wiki/File:FOS_Protectron_hostile.png), [original PNG](https://static.wikia.nocookie.net/fallout/images/7/79/FOS_Protectron_hostile.png) | Downloaded and visually inspected: correctly posed complete Shelter character, but the image includes a room background and health bar. Needs background/HUD removal; it is not a transparent drop-in. |
| Eyebot | [Screenshot source](https://www.reddit.com/r/falloutshelter/comments/1rpl9gf/screenshot_shelter_have_functional_eyebot_model/), [original PNG](https://i.redd.it/07eftadct4og1.png) | Downloaded and visually inspected: the robot on the right is complete and unobstructed, with correct antenna and lower assembly placement. Needs a cutout from the screenshot. |

A matching ready-transparent Shelter-style pair was **not verified**. These references are Fallout game
imagery, not CC0 assets. Keep their provenance distinct from the open-license effect packs. The Spriters
Resource Protectron/Eyebot listings are parts sheets and do not solve the request for complete posed images.

## Validation when implementing

- Check all 136 weapon rows resolve to the 11 supported pairs; unarmed adds the twelfth skill entry. Test
  canonical family normalization and the exceptions above, especially Power fist, Gatling laser and Junk Jet.
- Exercise all four races and supported states with power armor on/off. Verify human presentation for Gen III
  synths and unchanged animation behavior for every non-power-armor outfit.
- Preserve one synchronized impact for each authoritative action, including cosmetic bursts, multi-target
  skills and skill followed by normal attack. Do not add unreported misses, knockback, blocks or status effects.
- Check readable small icons in meters, preview and journal; left/right facing; no meter obstruction or layout
  shift; 390px/1280px viewports; reduced motion; and catch-up playback with readable attacker/target cues.
- Keep the playback regression cases for duplicate delivery, stale HP, healing, actor return, reset/navigation,
  account changes and final-result ordering. Skill visuals remain disabled for incidents.
