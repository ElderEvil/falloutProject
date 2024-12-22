import type { Room, Vault } from '@/types/vault'
import type { GridPosition } from '@/types/grid'

export interface RoomConfig {
  type: Room['type']
  label: string
  description: string
  requiredDwellers: number
  cost: number
  size: number
}

export const ROOM_CONFIGS: RoomConfig[] = [
  {
    type: 'power',
    label: 'POWER GENERATOR',
    description: 'Generates power for vault operations',
    requiredDwellers: 2,
    cost: 100,
    size: 1
  },
  {
    type: 'water',
    label: 'WATER TREATMENT',
    description: 'Processes and purifies water',
    requiredDwellers: 2,
    cost: 100,
    size: 1
  },
  {
    type: 'food',
    label: 'FOOD PRODUCTION',
    description: 'Produces food for vault dwellers',
    requiredDwellers: 2,
    cost: 150,
    size: 1
  },
  {
    type: 'living',
    label: 'LIVING QUARTERS',
    description: 'Housing for vault dwellers',
    requiredDwellers: 0,
    cost: 100,
    size: 1
  }
]

export function getRoomConfig(type: Room['type']): RoomConfig {
  return ROOM_CONFIGS.find((config) => config.type === type) || ROOM_CONFIGS[0]
}

export function createVaultDoor(): Room {
  return {
    id: 0,
    type: 'living',
    level: 1,
    capacity: 2,
    dwellers: [],
    position: { x: 0, y: 0 },
    size: 1
  }
}

export function isVaultDoor(room: Room): boolean {
  return room.id === 0
}

export function getRoomCapacityBySize(size: number): number {
  return size * 2
}

export function findAdjacentRooms(
  vault: Vault,
  position: GridPosition,
  type: Room['type']
): Room[] {
  const adjacentRooms: Room[] = []
  const { x, y } = position

  // Check left
  if (x > 0) {
    const leftCell = vault.grid[y][x - 1]
    if (leftCell.status === 'occupied' && leftCell.roomId) {
      const leftRoom = vault.rooms.find((r) => r.id === leftCell.roomId)
      if (leftRoom && leftRoom.type === type && !isVaultDoor(leftRoom)) {
        adjacentRooms.push(leftRoom)
      }
    }
  }

  // Check right
  if (x < vault.grid[0].length - 1) {
    const rightCell = vault.grid[y][x + 1]
    if (rightCell.status === 'occupied' && rightCell.roomId) {
      const rightRoom = vault.rooms.find((r) => r.id === rightCell.roomId)
      if (rightRoom && rightRoom.type === type && !isVaultDoor(rightRoom)) {
        adjacentRooms.push(rightRoom)
      }
    }
  }

  return adjacentRooms
}

export function canMergeRooms(vault: Vault, position: GridPosition, type: Room['type']): boolean {
  const adjacentRooms = findAdjacentRooms(vault, position, type)
  if (adjacentRooms.length === 0) return false

  // Calculate total width including new room and existing rooms
  const totalWidth = adjacentRooms.reduce((sum, room) => sum + room.size, 1)
  return totalWidth <= 3 // Maximum width is 3
}

export function mergeRooms(
  vault: Vault,
  position: GridPosition,
  type: Room['type'],
  newRoomId: number
): Room {
  const adjacentRooms = findAdjacentRooms(vault, position, type)

  // Create merged room
  const mergedRoom: Room = {
    id: newRoomId,
    type,
    level: 1,
    capacity: getRoomCapacityBySize(adjacentRooms.reduce((sum, room) => sum + room.size, 1)),
    dwellers: adjacentRooms.reduce(
      (allDwellers, room) => [...allDwellers, ...room.dwellers],
      [] as Room['dwellers']
    ),
    position: {
      x: Math.min(...adjacentRooms.map((r) => r.position.x), position.x),
      y: position.y
    },
    size: adjacentRooms.reduce((sum, room) => sum + room.size, 1)
  }

  // Remove old rooms
  vault.rooms = vault.rooms.filter((r) => !adjacentRooms.some((ar) => ar.id === r.id))

  // Update grid cells
  for (let i = 0; i < mergedRoom.size; i++) {
    const cell = vault.grid[position.y][mergedRoom.position.x + i]
    cell.status = 'occupied'
    cell.roomId = mergedRoom.id
  }

  return mergedRoom
}
