// Artwork keys and the corresponding exploration/arena catalog keys.
// Model scale is relative to a dweller (1). Keep creature proportions here so
// scene rendering can change without duplicating per-species sizing rules.
// The combat scene supplies one shared, scene-relative body height.
const MODEL_SIZE_CLASSES = {
  0.5: 'size-[calc(var(--scene-actor-height,7rem)*0.5)]',
  0.7: 'size-[calc(var(--scene-actor-height,7rem)*0.7)]',
  0.8: 'size-[calc(var(--scene-actor-height,7rem)*0.8)]',
  1: 'size-[var(--scene-actor-height,7rem)]',
  1.18: 'size-[calc(var(--scene-actor-height,7rem)*1.18)]',
  1.3: 'size-[calc(var(--scene-actor-height,7rem)*1.3)]',
  1.5: 'size-[calc(var(--scene-actor-height,7rem)*1.5)]',
} as const

export const RAIDER_VARIANTS = ['sable', 'rook', 'jinx', 'gristle', 'brick', 'cutter'] as const
const RAIDER_ASSET_VERSION = '5'

export const raiderVariantPath = (seed = 0): string =>
  `/static/raider_images/variants/${RAIDER_VARIANTS[Math.abs(seed) % RAIDER_VARIANTS.length]}.webp?v=${RAIDER_ASSET_VERSION}`

export const creatureSeed = (value: string): number => {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0
  }
  return hash
}

export const CREATURE_ASSETS = (
  [
    { name: 'Deathclaw', key: 'deathclaw', modelScale: 1.5, arenaKey: 'deathclaw' },
    { name: 'Feral Ghoul', key: 'feral-ghoul', modelScale: 1, arenaKey: 'feral-ghoul' },
    {
      name: 'Raider',
      key: 'raider',
      modelScale: 1,
      arenaKey: 'raider',
      generated: true,
      image: raiderVariantPath(0),
    },
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
    image?: string
  }>
).map((asset) => ({
  ...asset,
  image: asset.image ?? asset.originalImage ?? `/static/creature_images/assembled/${asset.key}.webp`,
  sourceImage: asset.generated
    ? undefined
    : (asset.originalImage ?? `/static/creature_images/${asset.key}.png`),
}))

const getCreatureAsset = (key: string) =>
  CREATURE_ASSETS.find((asset) => asset.arenaKey === key || asset.key === key)

export const getCreatureImagePath = (key: string, seed = 0): string | undefined =>
  key === 'raider' || key === 'raider-gang' ? raiderVariantPath(seed) : getCreatureAsset(key)?.image

export const getActorModelSizeClass = (scale: number): string =>
  MODEL_SIZE_CLASSES[scale as keyof typeof MODEL_SIZE_CLASSES] ?? MODEL_SIZE_CLASSES[1]

export const getCreatureModelSizeClass = (key: string): string =>
  getActorModelSizeClass(getCreatureAsset(key)?.modelScale ?? 1)
