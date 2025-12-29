import type { components } from '@/types/api.generated'

// Re-export generated API types
export type Room = components['schemas']['RoomRead']
export type RoomCreate = components['schemas']['RoomCreate']
export type RoomUpdate = components['schemas']['RoomUpdate']
