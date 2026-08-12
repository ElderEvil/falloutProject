import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

// This is a global display preference, not room-domain state. Keeping it in
// core lets settings and room views share the same value without a profile →
// rooms dependency.
const showRoomImages = useLocalStorage('room-rendering:show-images', true)

export function useRoomRendering() {
  function toggleRoomImages() {
    showRoomImages.value = !showRoomImages.value
  }

  function setRoomImagesVisible(visible: boolean) {
    showRoomImages.value = visible
  }

  return {
    showRoomImages: computed(() => showRoomImages.value),
    toggleRoomImages,
    setRoomImagesVisible,
  }
}
