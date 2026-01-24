import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type Room = components['schemas']['RoomRead']
export type RoomCreate = components['schemas']['RoomCreate']
export type RoomUpdate = components['schemas']['RoomUpdate']
export type RoomTemplate = components['schemas']['RoomCreateWithoutVaultID']
