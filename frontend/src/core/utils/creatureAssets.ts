// Artwork keys and the corresponding exploration/arena catalog keys.
export const CREATURE_ASSETS = [
  { name: 'Deathclaw', key: 'deathclaw', arenaKey: 'deathclaw' },
  { name: 'Feral Ghoul', key: 'feral-ghoul', arenaKey: 'feral-ghoul' },
  { name: 'Mole Rat', key: 'mole-rat', arenaKey: 'mole-rat-pack' },
  { name: 'Radscorpion', key: 'radscorpion', arenaKey: 'giant-radscorpion' },
  { name: 'Radroach', key: 'radroach', arenaKey: 'radroach-swarm' },
  { name: 'Eyebot', key: 'eyebot', arenaKey: 'training-eyebot' },
  { name: 'Protectron', key: 'protectron', arenaKey: 'training-protectron' },
  { name: 'Mr. Handy', key: 'mr-handy', arenaKey: 'training-mr-handy' },
  { name: 'Yao Guai', key: 'yao-guai', arenaKey: 'yao-guai', generated: true },
  { name: 'Mirelurk', key: 'mirelurk', arenaKey: 'mirelurk', generated: true },
  { name: 'Bloatfly', key: 'bloatfly', arenaKey: 'bloatfly', generated: true },
  { name: 'Radstag', key: 'radstag', arenaKey: 'radstag', generated: true },
  { name: 'Night Stalker', key: 'night-stalker', arenaKey: 'night-stalker', generated: true },
].map((asset) => ({
  ...asset,
  image: `/static/creature_images/assembled/${asset.key}.webp`,
  sourceImage: asset.generated ? undefined : `/static/creature_images/${asset.key}.png`,
}))

export const getCreatureImagePath = (key: string): string | undefined =>
  CREATURE_ASSETS.find((asset) => asset.arenaKey === key || asset.key === key)?.image
