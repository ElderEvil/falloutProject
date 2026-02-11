import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

/**
 * Composable for room rendering preferences
 *
 * Allows users to toggle room image display for performance or aesthetic preferences
 */
export function useRoomRendering() {
  // Show/hide room background images
  const showRoomImages = useLocalStorage('room-rendering:show-images', true)

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
