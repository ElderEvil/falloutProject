# Fallout Shelter quest characters — reference

Source: <https://fallout.fandom.com/wiki/Fallout_Shelter_characters#Quest_characters> (Nukapedia, CC-BY-SA).
Snapshot of the quest-NPC roster for content planning: who exists in FOS canon, which quest they anchor,
and what role they play. Only 12 of 50 have any wiki image, and those are game screenshots, not portrait
art — there is nothing to vendor as dweller portraits here.

At the 2026-09-28 snapshot, none of these 50 appeared in our quest/event data. Later adaptations are
documented below. The six
TV-series quest rewards that ARE playable live in `backend/app/data/dwellers/quest_rewards.json`
(Lucy MacLean, The Ghoul, Maximus, Ma June, Snip Snip, Snake Oil Salesman); CX404 moved to pets.

| Character | Quest | Role | Location | Wiki image |
|---|---|---|---|---|
| Alvarado | Springtime for Atom | Confessor |  | no |
| Alvarez | The Road to Vaultopolis | Overseer | Vault 813 | yes |
| Artie Moore | A Thirst for Adventure | Explorer, scavenger |  | no |
| Bash | Bounty: Bash | Enemy raider |  | no |
| Beef Slam Bednarski | Monday Night Brawl | Raider boss |  | no |
| Big Wes | The Final Hunt | Hunter, enemy |  | no |
| Bigsby | The Tail Continues | Detective |  | no |
| Bigsby Brown | The Bigsby Brown Case | Detective |  | no |
| Boss McScrooge | Christmas at the Raider Camp | Raider | Raider camp | yes |
| Brother Will | The Sixth Sun | Church initiate | Raider camp | yes |
| Butcher | Bounty: Butcher | Enemy deathclaw |  | no |
| Chang | All Work and No Play | Overseer | Vault 700 | no |
| Chef | By Hook or by Cook | Chef, enemy | Abandoned Red Rocket | no |
| Coach | Worst. Coach. Ever.
Here's to You, Rackie Jobinson | Enemy raider |  | no |
| Cruddy Bonez | Aqua-schema | Gang leader |  | no |
| Drusilla | Set 'em Up: Famine
Knock 'Em Down | Ghoul |  | no |
| Eli Calvert | Out of the Vault, Into the Shadows | Raider |  | yes |
| Emma | The Tail Continues | Overseer |  | no |
| Frank the Tank | Tankbusting | Raider | Vault 333 | yes |
| Hatchet O'Houlihan | Monday Night Brawl | Raider boss |  | no |
| Henrietta | Time for a Grand Slam? | Ex-girlfriend | Vault 232 | no |
| Herb Vest | Go West | Lost character | Old candy factory | no |
| Howard Phillips | Halloween (Non)Fiction | Library caretaker | Ruined library | no |
| Khan Killian | KHAAANNNNN!!!! | Great Khan | Random mine | no |
| Knight Sanducci | No Stone Unturned | Maxson's Roughnecks member | Poseidon Energy offices | no |
| Mandy Macintosh | Paula's in a Pickle! | Explorer, scavenger |  | yes |
| Marcus Hammer | Wedding Crashers | Raider, Groom |  | no |
| Mastiff Muldoon | Kidnapping at Vault 778 | Enemy | Vault 778 | no |
| Mole Rat Man | The Mole Rat Man | Scientist, enemy |  | no |
| Nicholas | Santa's Helpers | Overseer |  | no |
| Otto von Hurfburg | Wonders of TechnologyWonders of ScienceWonders of Nature | Scientist |  | yes |
| Patel | Into Vault 333! | Overseer | Vault 333 | yes |
| Paula Plumbkin | Journey to the Center of Vaultopolis | Raider, former vault dweller | Vault 525 | yes |
| Queen of the Deathclaws | Queen of the Deathclaws! | Deathclaw raiser, raider boss |  | no |
| Radroach Rodney | Reign of Radroach Rodney! | Enemy raider |  | no |
| Radscorpion Earl | The Scorpion... King? | Entrepreneur | Earl's radscorpion emporium | no |
| Red Rachel | Den of Thieves | Raider boss |  | no |
| Regina Rage | Return to Vault 333 | Enemy raider | Vault 333 | yes |
| Road Rash | Raider Troubles at Corvega | Enemy raider |  | no |
| Rubarb Mitchell | Rubarb's Reckoning | Rogue vault dweller | Vault 711 | no |
| Sally Switchblade | Wedding Crashers | Raider, Bride |  | no |
| Slugger | Take Me out to the Ball Game | Raider |  | yes |
| Snips | Bounty: Snips | Enemy radscorpion |  | no |
| Steve "Shadow Wolf" | The Shadow Wolf | Tracker |  | no |
| Stuart Monaghan | A Pale Imitation | Overseer | Vault R41D | no |
| The Embalmer | Monday Night Brawl | Raider boss |  | no |
| Willard Glover | With Friends Like These | Raider | Corvega Factory | no |
| Wizard of Water | Snake Water | Salesman | Dilapidated factory | no |
| Wyatt | Bunker Down | Railroad leader | Railroad bunker | yes |
| Yak | Bounty: Yak | Mole rat brood mother |  | no |

## Playable questline adaptations

The JSON catalog now includes these three independent chains, adding 13 quests. Their first missions
use the existing Overseer's Office gate; later missions require claiming the previous mission's rewards.
No unimplemented cross-chain prerequisite is advertised.

| Chain | Quests | Party level gates | Outbound duration | Finale rewards |
|---|---:|---|---|---|
| Almost Human | 4 | 15, 20, 30, 40 | 45–120 minutes | Harkness, T-45a power armor, 1,500 caps |
| Climbing the Ranks | 4 | 20, 24, 27, 35 | 60–120 minutes | Sarah Lyons, Sturdy combat armor, 1,600 caps |
| A Settler Needs Your Help | 5 | 40, 42, 45, 47, 50 | 90–150 minutes | Preston Garvey, 8 Stimpaks, 2,200 caps |

Sources: [Almost Human](https://fallout.fandom.com/wiki/Almost_Human),
[Climbing the Ranks](https://fallout.fandom.com/wiki/Climbing_the_Ranks), and
[A Settler Needs Your Help](https://fallout.fandom.com/wiki/A_Settler_Needs_Your_Help),
Fallout Wiki / Nukapedia contributors (CC-BY-SA). Quest names, ordering and story premises follow those
references; the descriptions are newly written for this project.

Balance and implementation differences from Fallout Shelter:

- Level gates follow the source chains. Durations are explicitly shortened for this project's pacing;
  the normal return journey is added by the existing quest service.
- Weapon gates use our equipped weapon's average damage, with explicit mandatory `ATTACK` requirements.
  Almost Human uses 4/7/10/13, Climbing the Ranks uses 5/9/10/12, and the settler chain uses 12/13/14/15/16.
  Level and attack counts both use the existing minimum-one-party-member rule.
- Recipe fragments and random loot tables are replaced with guaranteed catalog equipment, treatment
  supplies and caps. Gear payouts retain each item's catalog rarity. Earlier missions supply useful
  weapons for later damage gates; the rescue story does not create a new combat or dialogue mechanic.
- Harkness is an additional, project-specific rescue reward in Almost Human. All three finale recruits
  use existing named templates, population-capacity checks, and duplicate-template fallback behaviour.
- Sources are content references, not live dependencies. Versioned JSON is loaded by the normal startup
  seeder, including existing vaults; no migration or external request is needed to add these quests.
