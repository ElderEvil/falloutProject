import type { Vault } from '@/types/vault.types'

export function createDwellerManager(getVault: () => Vault | null) {
  function assignDwellerToRoom(dwellerId: string, roomId: string) {
    const vault = getVault()
    if (!vault) return false

    const dweller = vault.dwellers.find((d) => d.id === dwellerId)
    const room = vault.rooms.find((r) => r.id === roomId)

    if (!dweller || !room || !room.capacity) return false
    if (room.dwellers.length >= room.capacity) return false

    // Remove dweller from previous room if assigned
    if (dweller.room_id) {
      const previousRoom = vault.rooms.find((r) => r.dwellers.some((d) => d.id === dwellerId))
      if (previousRoom) {
        previousRoom.dwellers = previousRoom.dwellers.filter((d) => d.id !== dwellerId)
      }
    }

    // Assign dweller to new room
    dweller.room_id = roomId
    room.dwellers.push(dweller)

    return true
  }

  function unassignDweller(dwellerId: string) {
    const vault = getVault()
    if (!vault) return false

    const dweller = vault.dwellers.find((d) => d.id === dwellerId)
    if (!dweller) return false

    // Remove dweller from current room
    vault.rooms.forEach((room) => {
      room.dwellers = room.dwellers.filter((d) => d.id !== dwellerId)
    })

    return true
  }

  return {
    assignDwellerToRoom,
    unassignDweller
  }
}
