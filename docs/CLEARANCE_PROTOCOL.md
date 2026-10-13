# The Clearance Protocol

Issue #760: an ambiguous, Fallout-shaped homage to Hugh Howey's *Silo*. No Silo
characters, factions or canon are introduced. The Department of Exterior Continuity
is an invented pre-war bureaucracy; no account establishes the truth about its cameras,
volunteers, or alleged sabotage.

## First delivery

As an explorer, I discover contradictory procedures through places, biographies,
and exploration journal messages. The maintainer chose descriptive clues on 2026-10-13.
KISS/YAGNI: no collectible inventory category, dossier unlock, new quest, crafting use,
combat bonus, or reward token. Ordinary rest events retain their existing healing reward.

| Place | Group | Explicit registration route when template is recruited |
|---|---|---|
| The Outlook Station | observation_facility | Laurel Divinitus's curated visited_places |
| The Mile-Deep Shelter | vertical_refuge | Martha Dewey's curated visited_places |
| The Heartworks | power | Tina Wrenchley's curated visited_places |

Normal template creation registers these visited places through DwellerService →
MapService. This guarantees registration when the named template is recruited; recruitment
of that template is not guaranteed for every vault. Deploy with the normal place-seeding
command. This PR does not mutate production or rewrite already instantiated biographies.

## Relics as readable clues

Existing place descriptions are the content store for this delivery:

- **Exterior lens cloth, clearance suit patch, sealed cleaning kit, optics checklist:**
  Outlook records call volunteer maintenance both voluntary and mandatory. A returned
  suit patch at the Mile-Deep Shelter conflicts with the story of a one-way duty.
- **The Continuity Compact:** competing fragments authorize and forbid departure.
  Heartworks fragments disagree about whether the plant stopped or must never stop.
- **Thermal Seal Tape / Department-Issue Heat Tape:** two labels for one maintenance
  material. A replacement notice's sealed specifications suggest several explanations,
  including ordinary bad procurement.

These are named narrative objects, not grantable Weapon/Outfit/Junk rows. No item-factory
or reward classification extension is needed. Future collectible work must define
persistence, reveal UI and duplicate handling before creating catalog rows.

## Runtime flavor

Three unresolved lines join the existing optional bio-rumor pool. Reusing
`zone_rumor_chance` avoids another roll or balance setting; keep that existing config name
for compatibility. Quiet Zone rumors remain available.

Four rest-event templates mention protocol clues. Each retains `{health}` and the existing
RestEventSchema behavior. Journal prose does not assert site discovery; map discovery uses
the explicit visited_places routes above. Existing progression surfacing is unchanged.

## Verification

Focused content tests resolve groups, require a curated route to every named place,
validate all rest-template placeholders, and require relics/fragments/tape in readable
place descriptions. Place-group/seed, bio and exploration-generator suites cover reused paths.
