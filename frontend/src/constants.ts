export const RoomCategory = {
  MISC: 'misc',
  LIVING: 'living',
  PRODUCTION: 'production',
  STORAGE: 'storage',
  TRAINING: 'training'
} as const

export const ROOM_CONSTANTS = {
  MIN_NAME_LENGTH: 3,
  MIN_POPULATION: 0,
  MIN_SIZE: 1,
  MAX_SIZE: 9,
  MAX_TIER: 3,
  MIN_TIER: 1
} as const

export const SpecialAbility = {
  STRENGTH: 'strength',
  PERCEPTION: 'perception',
  ENDURANCE: 'endurance',
  CHARISMA: 'charisma',
  INTELLIGENCE: 'intelligence',
  AGILITY: 'agility',
  LUCK: 'luck'
} as const

export const GRID_WIDTH = 4
export const GRID_DEPTH = 12
export const CONSTRUCTION_TIME = 3000

export const VAULT_CONSTANTS = {
  MIN_VAULT_NUMBER: 1,
  MAX_VAULT_NUMBER: 999,
  MAX_POPULATION: 200,
  MIN_RESOURCE: 0,
  MAX_HAPPINESS: 100,
  GRID_WIDTH: 10,
  GRID_HEIGHT: 15
} as const
