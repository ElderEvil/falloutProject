import type { components } from '@/types/api.generated'

// Re-export generated API types
// Dweller is the full type with all relations (vault, room, weapon, outfit)
export type Dweller = components['schemas']['DwellerReadFull']
export type DwellerFull = components['schemas']['DwellerReadFull']
export type DwellerShort = components['schemas']['DwellerReadLess']
export type DwellerCreate = components['schemas']['DwellerCreate']
export type DwellerUpdate = components['schemas']['DwellerUpdate']

// Helper type for SPECIAL stats
export interface Special {
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}

// Visual attributes type matching backend schema
export interface VisualAttributes {
  height?: string | null
  eye_color?: string | null
  appearance?: string | null
  skin_tone?: string | null
  build?: string | null
  hair_style?: string | null
  hair_color?: string | null
  distinguishing_features?: string[] | null
  clothing_style?: string | null
  facial_hair?: string | null
  makeup?: string | null
}
