import { computed, ref } from 'vue'
import { apiGet } from '@/core/utils/api'
import { handleStoreError } from '@/core/utils/errorHandler'

interface GameBalanceResponse {
  resource?: {
    base_production_rate?: number
  }
}

// Live backend value; null until /balance answers. No hardcoded fallback so the
// room UI can never drift from ResourceConfig again (see useRoomProduction).
const baseProductionRateSetting = ref<number | null>(null)
let loadPromise: Promise<void> | null = null

function loadGameBalance(): void {
  if (baseProductionRateSetting.value !== null || loadPromise !== null) return
  loadPromise = apiGet<GameBalanceResponse>('/api/v1/game/balance')
    .then((settings) => {
      const rate = settings?.resource?.base_production_rate
      if (typeof rate === 'number') baseProductionRateSetting.value = rate
    })
    .catch((error: unknown) => {
      handleStoreError(error, 'Failed to load game balance settings', false)
    })
    .finally(() => {
      loadPromise = null
    })
}

export function useGameBalance() {
  loadGameBalance()
  return { baseProductionRate: computed(() => baseProductionRateSetting.value) }
}
