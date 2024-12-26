import type { Room } from '@/types/room.types'

export interface RoomConfig {
  category: Room['category']
  label: string
  description: string
  requiredDwellers: number
  cost: number
  size: number
}
