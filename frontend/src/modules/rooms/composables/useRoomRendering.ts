import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

// Module-scoped room images preference (shared across all consumers)
const showRoomImages = useLocalStorage('room-rendering:show-images', true)

/**
 * Composable for room rendering preferences
 *
 * Allows users to toggle room image display for performance or aesthetic preferences
 */
export function useRoomRendering() {
  /**
   * Toggle room images on/off
   */
  function toggleRoomImages() {
    showRoomImages.value = !showRoomImages.value
  }

  /**
   * Set room images visibility
   */
  function setRoomImagesVisible(visible: boolean) {
    showRoomImages.value = visible
  }

  return {
    // State
    showRoomImages: computed(() => showRoomImages.value),

    // Actions
    toggleRoomImages,
    setRoomImagesVisible,
  }
}
