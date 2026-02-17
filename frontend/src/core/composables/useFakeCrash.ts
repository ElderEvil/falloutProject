import { ref } from 'vue'
import { useLocalStorage } from '@vueuse/core'

const CLICK_THRESHOLD = 7
const CLICK_TIMEOUT_MS = 2000
const STORAGE_KEY = 'fallout_crash_unlocked'

const isCrashing = ref(false)
const crashUnlocked = useLocalStorage(STORAGE_KEY, false)

let clickCount = ref(0)
let clickTimer: NodeJS.Timeout | null = null

export function useFakeCrash() {
  const handleVersionClick = () => {
    clickCount.value++

    if (clickTimer) clearTimeout(clickTimer)

    if (clickCount.value >= CLICK_THRESHOLD) {
      triggerFakeCrash()
      clickCount.value = 0
    } else {
      clickTimer = setTimeout(() => {
        clickCount.value = 0
      }, CLICK_TIMEOUT_MS)
    }
  }

  const triggerFakeCrash = () => {
    if (isCrashing.value) return

    crashUnlocked.value = true
    isCrashing.value = true
  }

  const resetCrash = () => {
    isCrashing.value = false
  }

  const resetCrashUnlocked = () => {
    crashUnlocked.value = false
  }

  return {
    isCrashing,
    crashUnlocked,
    clickCount,
    handleVersionClick,
    triggerFakeCrash,
    resetCrash,
    resetCrashUnlocked,
  }
}
