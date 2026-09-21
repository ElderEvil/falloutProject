export interface SpecialGuideEntry {
  letter: string
  label: string
  tagline: string
  effects: string[]
}

/** Short hybrid taglines (room/output first, Fallout voice second) for stat cards. */
export const SPECIAL_TAGLINES: Record<string, string> = {
  Strength: 'Brute force — power rooms and melee',
  Perception: 'Sharp eyes — water production and caps',
  Endurance: 'Grit — shrugs damage, roams farther',
  Charisma: 'Charm — radio recruits and relationships',
  Intelligence: 'Smarts — medbay output and energy weapons',
  Agility: 'Quick hands — food production and combat speed',
  Luck: 'Fortune — rare loot and fat caps',
}

/** Detailed overseer overview: strictly what each stat feeds mechanically. */
export const SPECIAL_GUIDE: SpecialGuideEntry[] = [
  {
    letter: 'S',
    label: 'Strength',
    tagline: SPECIAL_TAGLINES.Strength,
    effects: [
      'Power room output scales with Strength',
      'Melee damage weight in combat',
      'Half of exploration combat power (with Agility)',
    ],
  },
  {
    letter: 'P',
    label: 'Perception',
    tagline: SPECIAL_TAGLINES.Perception,
    effects: [
      'Water Treatment output scales with Perception',
      'More caps found while exploring',
      'Spots traps and trouble in expedition sites',
    ],
  },
  {
    letter: 'E',
    label: 'Endurance',
    tagline: SPECIAL_TAGLINES.Endurance,
    effects: [
      'Reduces damage taken (twice its value off enemy hits)',
      'High Endurance extends expeditions (stamina bonus)',
    ],
  },
  {
    letter: 'C',
    label: 'Charisma',
    tagline: SPECIAL_TAGLINES.Charisma,
    effects: [
      'Each point speeds radio recruitment (+5%)',
      'Radio room output scales with Charisma',
      'High Charisma on both sides speeds relationship affinity',
    ],
  },
  {
    letter: 'I',
    label: 'Intelligence',
    tagline: SPECIAL_TAGLINES.Intelligence,
    effects: [
      'Medbay and Science output (stimpaks, radaways)',
      'Energy weapon damage weight in combat',
    ],
  },
  {
    letter: 'A',
    label: 'Agility',
    tagline: SPECIAL_TAGLINES.Agility,
    effects: [
      'Diner output scales with Agility',
      'Other half of exploration combat power (with Strength)',
    ],
  },
  {
    letter: 'L',
    label: 'Luck',
    tagline: SPECIAL_TAGLINES.Luck,
    effects: [
      'Shifts loot rarity upward',
      'More caps while exploring',
    ],
  },
]

export const SPECIAL_BARS_GUIDE =
  'Striped segments are outfit and identity bonuses — uncapped, floored at 1, removable. ' +
  'An amber tick marks where a penalty dragged a stat below base. Numbers always rule over bars.'
