import type { Room, Vault } from '@/types/vault'
import type { GridPosition } from '@/types/grid'
import { canMergeRooms, getRoomCapacityBySize, mergeRooms } from '@/utils/roomUtils'

export function createRoomManager(
  getVault: () => Vault | null,
  unassignDweller: (dwellerId: string) => boolean
) {
  function startDigging(position: GridPosition) {
    const vault = getVault()
    if (!vault) return false

    const cell = vault.grid[position.y][position.x]
    if (cell.status !== 'empty') return false

    cell.status = 'digging'
    cell.progress = 0
    return true
  }

  function completeDigging(position: GridPosition) {
    const vault = getVault()
    if (!vault) return false

    const cell = vault.grid[position.y][position.x]
    if (cell.status !== 'digging') return false

    cell.status = 'ready'
    cell.progress = undefined
    return true
  }

  function startConstruction(position: GridPosition) {
    const vault = getVault()
    if (!vault) return false

    const cell = vault.grid[position.y][position.x]
    if (cell.status !== 'ready') return false

    cell.status = 'constructing'
    cell.progress = 0
    return true
  }

  function addRoom(type: Room['type'], position: GridPosition) {
    const vault = getVault()
    if (!vault) return false

    const cell = vault.grid[position.y][position.x]
    if (cell.status !== 'constructing') return false

    const newRoomId = Date.now()

    // Check if we can merge with adjacent rooms
    if (canMergeRooms(vault, position, type)) {
      const mergedRoom = mergeRooms(vault, position, type, newRoomId)
      vault.rooms.push(mergedRoom)
      return true
    }

    // Create new single room if no merging possible
    const newRoom: Room = {
      id: newRoomId,
      type,
      level: 1,
      capacity: getRoomCapacityBySize(1),
      dwellers: [],
      position,
      size: 1
    }

    vault.grid[position.y][position.x].status = 'occupied'
    vault.grid[position.y][position.x].roomId = newRoom.id
    vault.grid[position.y][position.x].progress = undefined

    vault.rooms.push(newRoom)
    return true
  }

  function destroyRoom(roomId: number) {
    const vault = getVault()
    if (!vault) return false

    const roomIndex = vault.rooms.findIndex((r) => r.id === roomId)
    if (roomIndex === -1) return false

    const room = vault.rooms[roomIndex]

    // Unassign all dwellers from the room
    room.dwellers.forEach((dweller) => {
      unassignDweller(dweller.id)
    })

    // Update all cells the room occupied
    for (let i = 0; i < room.size; i++) {
      const cell = vault.grid[room.position.y][room.position.x + i]
      cell.status = 'ready'
      cell.roomId = null
    }

    // Remove the room
    vault.rooms.splice(roomIndex, 1)
    return true
  }

  function getRoomById(roomId: number) {
    const vault = getVault()
    if (!vault) return null
    return vault.rooms.find((r) => r.id === roomId) || null
  }

  return {
    startDigging,
    completeDigging,
    startConstruction,
    addRoom,
    destroyRoom,
    getRoomById
  }
}
