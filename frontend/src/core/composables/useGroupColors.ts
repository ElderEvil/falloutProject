import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

// World-map marker colour mode: per-site-family tint by default, since five
// families the eye can sort beat nineteen hues nobody can decode. A display
// preference like the badge palette, so it lives on the Preferences page rather
// than the map toolbar; one shared ref keeps every reader in sync.
const groupColors = useLocalStorage<boolean>('map:group-colors', true)

export function useGroupColors() {
  const setGroupColors = (enabled: boolean) => {
    groupColors.value = enabled
  }

  const toggleGroupColors = () => {
    setGroupColors(!groupColors.value)
  }

  return {
    groupColors: computed(() => groupColors.value),
    setGroupColors,
    toggleGroupColors,
  }
}
