import { computed, ref } from 'vue'
import { useRoomStore } from '@/stores/room'
import type { Room } from '@/models/room'

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
    const startX = roomSize <= 3 ? x : x - Math.floor(cellsCount / 2)
    return Array.from({ length: cellsCount }, (_, i) => ({ x: startX + i, y }))
  })

  const isValidPlacement = computed(() => {
    if (!hoverPosition.value || !roomStore.selectedRoom) return false
    return previewCells.value.every(
      (cell) =>
        cell.x >= 0 &&
        cell.x < 8 &&
        !roomStore.rooms.some(
          (room: Room) =>
            room.coordinate_x <= cell.x &&
            room.coordinate_x + Math.ceil(room.size / 3) > cell.x &&
            room.coordinate_y === cell.y
        )
    )
  })

  return {
    hoverPosition,
    handleHover,
    clearHover,
    previewCells,
    isValidPlacement
  }
}
