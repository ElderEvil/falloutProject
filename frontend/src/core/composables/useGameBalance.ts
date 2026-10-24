import { computed, ref } from 'vue'
import { ApiError, apiGet } from '@/core/utils/api'
import { handleStoreError } from '@/core/utils/errorHandler'

interface GameBalanceResponse {
  resource?: {
    base_production_rate?: number
  }
  rush?: {
    happiness_delta?: number
    xp_per_worker?: number
  }
}

const BALANCE_LOAD_ATTEMPTS = 3

// Live backend value; null until /balance answers. No hardcoded fallback so the
// room UI can never drift from ResourceConfig again (see useRoomProduction).
const baseProductionRateSetting = ref<number | null>(null)
const rushHappinessDeltaSetting = ref<number | null>(null)
const rushXpPerWorkerSetting = ref<number | null>(null)
let loadPromise: Promise<void> | null = null

async function fetchGameBalance(): Promise<void> {
  for (let attempt = 1; attempt <= BALANCE_LOAD_ATTEMPTS; attempt += 1) {
    try {
      const settings = await apiGet<GameBalanceResponse>('/api/v1/game/balance')
      const rate = settings?.resource?.base_production_rate
      if (typeof rate !== 'number')
        throw new Error('Game balance response has no base production rate')
      const happinessDelta = settings?.rush?.happiness_delta
      const xpPerWorker = settings?.rush?.xp_per_worker
      baseProductionRateSetting.value = rate
      rushHappinessDeltaSetting.value = typeof happinessDelta === 'number' ? happinessDelta : null
      rushXpPerWorkerSetting.value = typeof xpPerWorker === 'number' ? xpPerWorker : null
      return
    } catch (error: unknown) {
      if (attempt === BALANCE_LOAD_ATTEMPTS || !isRetryableBalanceError(error)) {
        handleStoreError(error, 'Failed to load game balance settings')
        return
      }
    }
  }
}

function isRetryableBalanceError(error: unknown): boolean {
  // Client errors repeat identically — only network failures (no status) and
  // server errors are worth another attempt.
  if (error instanceof ApiError) return error.status === null || error.status >= 500
  return true
}

function loadGameBalance(): void {
  if (baseProductionRateSetting.value !== null || loadPromise !== null) return
  loadPromise = fetchGameBalance().finally(() => {
    loadPromise = null
  })
}

export function useGameBalance() {
  loadGameBalance()
  return {
    baseProductionRate: computed(() => baseProductionRateSetting.value),
    rushHappinessDelta: computed(() => rushHappinessDeltaSetting.value),
    rushXpPerWorker: computed(() => rushXpPerWorkerSetting.value),
  }
}
