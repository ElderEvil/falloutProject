import type { GridCell } from '@/types/grid'

export interface Resource {
  type: 'power' | 'food' | 'water'
  amount: number
  capacity: number
}

export interface Special {
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}

export interface VisualAttributes {
  age: string
  build: string
  height: string
  eye_color: string
  skin_tone: string
  appearance: string
  hair_color: string
  hair_style: string
  clothing_style: string
}

export interface Dweller {
  id: string
  first_name: string
  last_name: string
  level: number
  experience: number
  health: number
  max_health: number
  radiation: number
  happiness: number
  stimpack: number
  radaway: number
  assigned: boolean
  roomId?: number
  special?: Special
  bio?: string
  is_adult?: boolean
  gender?: 'male' | 'female'
  rarity?: string
  visual_attributes?: VisualAttributes
  image_url?: string
  thumbnail_url?: string
  created_at?: string
  updated_at?: string
}

export interface Room {
  id: number
  type: 'living' | 'power' | 'water' | 'food'
  level: number
  capacity: number
  dwellers: Dweller[]
  position: {
    x: number
    y: number
  }
  size: number
}

export interface Vault {
  id: number
  name: string
  resources: Resource[]
  dwellers: Dweller[]
  maxDwellers: number
  rooms: Room[]
  bottlecaps: number
  grid: GridCell[][]
}
