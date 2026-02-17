import { ref } from 'vue'
import { useLocalStorage } from '@vueuse/core'

const GARY_DURATION_MS = 10000
const STORAGE_KEY = 'fallout_gary_unlocked'

const isGaryMode = ref(false)
const garyUnlocked = useLocalStorage(STORAGE_KEY, false)

let garyTimer: NodeJS.Timeout | null = null

export function useGaryMode() {
  const triggerGaryMode = () => {
    if (isGaryMode.value) return

    garyUnlocked.value = true
    isGaryMode.value = true

    if (garyTimer) clearTimeout(garyTimer)

    garyTimer = setTimeout(() => {
      isGaryMode.value = false
    }, GARY_DURATION_MS)
  }

  const resetGaryUnlocked = () => {
    garyUnlocked.value = false
  }

  return {
    isGaryMode,
    garyUnlocked,
    triggerGaryMode,
    resetGaryUnlocked,
  }
}
