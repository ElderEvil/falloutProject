// Mirrors app/options/appearance.py on the backend; keep the two in sync.

export const SKIN_TONE_OPTIONS: Record<string, string[]> = {
  human: ['Pale', 'Light', 'Tan', 'Brown', 'Dark Brown', 'Ebony'],
  ghoul: ['Pale Grey', 'Ashen', 'Mottled', 'Necrotic', 'Glowing'],
  super_mutant: ['Light Green', 'Green', 'Dark Green', 'Olive Green'],
  synth: ['Synthetic Fair', 'Synthetic Dark', 'Metallic Silver', 'Exposed Component'],
}

export const BUILD_OPTIONS: Record<string, string[]> = {
  human: ['Slim', 'Athletic', 'Muscular', 'Stocky', 'Average', 'Overweight'],
  ghoul: ['Skeletal', 'Withered', 'Twisted'],
  super_mutant: ['Muscular', 'Brutish', 'Towering'],
  synth: ['Slender', 'Muscular', 'Armored'],
}

export const HAIRCUT_OPTIONS: Record<string, string[]> = {
  human: [
    'Short Hair',
    'Long Hair',
    'Ponytail',
    'Mohawk',
    'Buzz Cut',
    'Curly Hair',
    'Bun',
    'Braided Hair',
    'Wavy Hair',
    'Dreadlocks',
  ],
  ghoul: [
    'Patchy Hair',
    'Stringy Hair',
    'Messy Hair',
    'Mohawk',
    'Burned Scalp',
    'Radiation-Scarred',
    'Thinning Hair',
    'Wispy Remains',
  ],
  super_mutant: [
    'Bald',
    'Scalp Ridges',
    'Patchy Tufts',
    'Mohawk',
    'Thick Stubble',
    'War Paint Scalp',
  ],
  synth: [
    'Clean Cut',
    'Slicked Back',
    'Military Precision Cut',
    'Exposed Circuits',
    'Synthetic Fiber Weave',
    'Metallic Sheen Hair',
  ],
}

export const HEADGEAR_OPTIONS: Record<string, string[]> = {
  human: [
    'Baseball Cap',
    'Bandana',
    'Combat Helmet',
    'Gas Mask',
    'Cowboy Hat',
    'Bowler Hat',
    'Fedora',
    'Ushanka',
    'Beanie',
    'Military Beret',
    'Newsboy Cap',
    'Vault-Tec Helmet',
    'Hooded Coat',
  ],
  ghoul: [
    'Tattered Bandana',
    'Raider Cage Mask',
    'Wrapped Head Bandages',
    'Radiation Suit Hood',
    'Scrapped Metal Helmet',
    'Faded Cap',
    'Glowing One Crown',
    'Leather Hood',
  ],
  super_mutant: [
    'Metal Helmet',
    'Spiked Helmet',
    'Chain Headdress',
    'Skull Trophy',
    'Heavy Plate Helmet',
    'Makeshift Face Guard',
    'Mutant Battle Helm',
  ],
  synth: [
    'Institute Hood',
    'Metallic Plating',
    'Stealth Field Generator',
    'Neural Interface Helmet',
    'Courser Hood',
    'Synth Component Display',
    'Reinforced Circuitry Cap',
  ],
}

export const HEIGHT_OPTIONS = ['tall', 'average', 'short'] as const
export const EYE_COLOR_OPTIONS = ['blue', 'green', 'brown', 'hazel', 'gray'] as const
export const HAIR_COLORS = [
  'blonde',
  'brunette',
  'black',
  'brown',
  'red',
  'gray',
  'white',
  'blue',
  'green',
  'pink',
] as const
export const EXPRESSIONS = [
  'neutral',
  'smiling',
  'laughing',
  'proud',
  'sad',
  'angry',
  'frustrated',
  'shocked',
  'terrified',
  'determined',
  'heroic',
  'stoic',
  'skeptical',
  'suspicious',
  'confused',
  'awkward',
  'mischievous',
  'flirty',
] as const
export const POSE_OPTIONS = [
  'Standing confidently',
  'Combat ready',
  'Checking Pip-Boy',
  'Faction salute',
  'Alert and wary',
  'Action shot',
  'Stealth crouch',
  'Power armor stance',
  'Wounded but resilient',
  'Weapon drawn',
  'Scavenging through debris',
] as const
export const BACKGROUND_OPTIONS = [
  'Vault Interior',
  'Wasteland Ruins',
  'Brotherhood Airship',
  'Super Mutant Camp',
  'Nuclear Crater',
  'Pre-War Suburb',
  'Red Rocket Station',
  'Settlement',
  'Abandoned Factory',
  'The Institute',
  'New Vegas Strip',
] as const
