// Artwork keys and the corresponding exploration/arena catalog keys.
// Model scale is relative to a dweller (1). Keep creature proportions here so
// scene rendering can change without duplicating per-species sizing rules.
const MODEL_SIZE_CLASSES = {
  0.5: 'h-10 w-10 sm:h-14 sm:w-14',
  0.7: 'h-14 w-14 sm:h-20 sm:w-20',
  1: 'h-20 w-20 sm:h-28 sm:w-28',
  1.3: 'h-26 w-26 sm:h-36 sm:w-36',
  1.5: 'h-30 w-30 sm:h-42 sm:w-42',
} as const

export const CREATURE_ASSETS = (
  [
    { name: 'Deathclaw', key: 'deathclaw', modelScale: 1.5, arenaKey: 'deathclaw' },
    { name: 'Feral Ghoul', key: 'feral-ghoul', modelScale: 1, arenaKey: 'feral-ghoul' },
    { name: 'Raider', key: 'raider', modelScale: 1, arenaKey: 'raider', generated: true },
    {
      name: 'Super Mutant',
      key: 'super-mutant',
      modelScale: 1.3,
      arenaKey: 'super-mutant',
      originalImage:
        '/static/dweller_images/variants/non_human/super_mutant/FOS_Dw_Default_SuperMutant_Male_Average_Alt.webp',
    },
    { name: 'Mole Rat', key: 'mole-rat', modelScale: 0.7, arenaKey: 'mole-rat-pack' },
    { name: 'Radscorpion', key: 'radscorpion', modelScale: 1.3, arenaKey: 'giant-radscorpion' },
    { name: 'Radroach', key: 'radroach', modelScale: 0.5, arenaKey: 'radroach-swarm' },
    { name: 'Eyebot', key: 'eyebot', modelScale: 0.7, arenaKey: 'training-eyebot' },
    { name: 'Protectron', key: 'protectron', modelScale: 1, arenaKey: 'training-protectron' },
    {
      name: 'Mr. Handy',
      key: 'mr-handy',
      modelScale: 1,
      arenaKey: 'training-mr-handy',
      originalImage: '/static/creature_images/originals/mr-handy.webp',
    },
    { name: 'Yao Guai', key: 'yao-guai', modelScale: 1.5, arenaKey: 'yao-guai', generated: true },
    { name: 'Mirelurk', key: 'mirelurk', modelScale: 1.3, arenaKey: 'mirelurk', generated: true },
    { name: 'Bloatfly', key: 'bloatfly', modelScale: 0.5, arenaKey: 'bloatfly', generated: true },
    { name: 'Radstag', key: 'radstag', modelScale: 1.3, arenaKey: 'radstag', generated: true },
    {
      name: 'Night Stalker',
      key: 'night-stalker',
      modelScale: 1,
      arenaKey: 'night-stalker',
      generated: true,
    },
  ] satisfies Array<{
    name: string
    key: string
    arenaKey: string
    modelScale: keyof typeof MODEL_SIZE_CLASSES
    generated?: boolean
    originalImage?: string
  }>
).map((asset) => ({
  ...asset,
  image: asset.originalImage ?? `/static/creature_images/assembled/${asset.key}.webp`,
  sourceImage: asset.generated
    ? undefined
    : (asset.originalImage ?? `/static/creature_images/${asset.key}.png`),
}))

const getCreatureAsset = (key: string) =>
  CREATURE_ASSETS.find((asset) => asset.arenaKey === key || asset.key === key)

export const getCreatureImagePath = (key: string): string | undefined =>
  getCreatureAsset(key)?.image

export const getCreatureModelSizeClass = (key: string): string =>
  MODEL_SIZE_CLASSES[getCreatureAsset(key)?.modelScale ?? 1]
