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
].map((asset) => ({
  ...asset,
  image: `/static/creature_images/assembled/${asset.key}.webp`,
  sourceImage: `/static/creature_images/${asset.key}.png`,
}))

export const getCreatureImagePath = (key: string): string | undefined =>
  CREATURE_ASSETS.find((asset) => asset.arenaKey === key || asset.key === key)?.image
