import { computed, ref } from 'vue'
import { useRoomStore } from '../stores/room'
import type { Room } from '../models/room'
import { hasElevatorAbove, isLevelBuildable } from '../utils/room'

export function useHoverPreview() {
  const roomStore = useRoomStore()
  const hoverPosition = ref<{ x: number; y: number } | null>(null)

  const handleHover = (x: number, y: number) => {
    if (roomStore.selectedRoom && roomStore.isPlacingRoom) {
      hoverPosition.value = { x, y }
    } else {
      hoverPosition.value = null
    }
  }

  const clearHover = () => {
    hoverPosition.value = null
  }

  const previewCells = computed(() => {
    if (!hoverPosition.value || !roomStore.selectedRoom) return []
    const { x, y } = hoverPosition.value
    const roomSize = roomStore.selectedRoom.size_min
    const cellsCount = Math.ceil(roomSize / 3)
    // Center the room preview on hover cell for multi-cell rooms
    const startX = cellsCount === 1 ? x : x - Math.floor(cellsCount / 2)
    return Array.from({ length: cellsCount }, (_, i) => ({ x: startX + i, y }))
  })

  const isValidPlacement = computed(() => {
    if (!hoverPosition.value || !roomStore.selectedRoom) return false
    const selected = roomStore.selectedRoom
    const isElevator = selected.name.toLowerCase() === 'elevator'
    return previewCells.value.every((cell) => {
      const inBounds = cell.x >= 0 && cell.x < 8
      if (!inBounds) return false
      const occupied = roomStore.rooms.some(
        (room: Room) =>
          (room.coordinate_x ?? 0) <= cell.x &&
          (room.coordinate_x ?? 0) + Math.ceil((room.size || room.size_min) / 3) > cell.x &&
          (room.coordinate_y ?? 0) === cell.y
      )
      if (occupied) return false
      if (isElevator) return hasElevatorAbove(roomStore.rooms, cell.x, cell.y)
      return isLevelBuildable(roomStore.rooms, cell.y)
    })
  })

  return {
    hoverPosition,
    handleHover,
    clearHover,
    previewCells,
    isValidPlacement,
  }
}
