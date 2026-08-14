import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type Room = components['schemas']['RoomRead']
export type RoomBuild = components['schemas']['RoomBuild']
export type RoomTemplate = components['schemas']['RoomCreateWithoutVaultID']
