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
    const selected = roomStore.selectedRoom
    const isElevator = selected.name.toLowerCase() === 'elevator'
    const cellsCount = isElevator ? 1 : selected.size_min
    return Array.from({ length: cellsCount }, (_, i) => ({ x: x + i, y }))
  })

  const isValidPlacementAt = (x: number, y: number) => {
    if (!roomStore.selectedRoom) return false
    const selected = roomStore.selectedRoom
    const isElevator = selected.name.toLowerCase() === 'elevator'
    const originX = x
    if (isElevator ? originX !== roomStore.shaftX : !roomStore.roomSlotStarts.includes(originX))
      return false
    const size = isElevator ? 1 : selected.size_min
    if (
      !isElevator &&
      !roomStore.rooms.some(
        (room) =>
          room.coordinate_y === y &&
          room.coordinate_x != null &&
          (room.coordinate_x + (room.size ?? room.size_min) === x || x + size === room.coordinate_x)
      )
    )
      return false
    return Array.from({ length: size }, (_, i) => ({ x: x + i, y })).every((cell) => {
      const inBounds = cell.x >= 0 && cell.x < roomStore.floorUnits
      if (!inBounds) return false
      const occupied = roomStore.rooms.some(
        (room: Room) =>
          (room.coordinate_x ?? 0) <= cell.x &&
          (room.coordinate_x ?? 0) + (room.size || room.size_min) > cell.x &&
          (room.coordinate_y ?? 0) === cell.y
      )
      if (occupied) return false
      if (isElevator) return hasElevatorAbove(roomStore.rooms, cell.x, cell.y)
      return isLevelBuildable(roomStore.rooms, cell.y)
    })
  }

  const isValidPlacement = computed(
    () => !!hoverPosition.value && isValidPlacementAt(hoverPosition.value.x, hoverPosition.value.y)
  )

  return {
    hoverPosition,
    handleHover,
    clearHover,
    previewCells,
    isValidPlacement,
    isValidPlacementAt,
  }
}
