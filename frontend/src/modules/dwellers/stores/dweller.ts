import { reactive } from 'vue'
import { getActivePinia } from 'pinia'

export type {
  DwellerStatus,
  DwellerAgeGroup,
  DwellerWithStatus,
  DwellerSortBy,
  SortDirection,
} from './dwellerFilter'

export { useDwellerFilterStore } from './dwellerFilter'

export { useDwellerGenerationStore } from './dwellerGeneration'
export { useDwellerManagementStore } from './dwellerManagement'
export { useDwellerMedicalStore } from './dwellerMedical'
export { useDwellerDeathStore } from './dwellerDeath'

import { useDwellerFilterStore } from './dwellerFilter'
import { useDwellerGenerationStore } from './dwellerGeneration'
import { useDwellerManagementStore } from './dwellerManagement'
import { useDwellerMedicalStore } from './dwellerMedical'
import { useDwellerDeathStore } from './dwellerDeath'

type DwellerFacade = ReturnType<typeof useDwellerFilterStore> &
  ReturnType<typeof useDwellerGenerationStore> &
  ReturnType<typeof useDwellerManagementStore> &
  ReturnType<typeof useDwellerMedicalStore> &
  ReturnType<typeof useDwellerDeathStore>

let cachedFacade: DwellerFacade | null = null
let cachedPinia: ReturnType<typeof getActivePinia> = null

function buildDwellerFacade(): DwellerFacade {
  const filter = useDwellerFilterStore()
  const generation = useDwellerGenerationStore()
  const management = useDwellerManagementStore()
  const medical = useDwellerMedicalStore()
  const death = useDwellerDeathStore()

  const stores = [filter, generation, management, medical, death]
  const keyToStore = new Map<string, unknown>()

  for (const store of stores) {
    for (const key of Object.keys(store)) {
      if (!keyToStore.has(key)) {
        keyToStore.set(key, store)
      }
    }
  }

  const target: Record<string, unknown> = {}

  for (const [key, store] of keyToStore.entries()) {
    Object.defineProperty(target, key, {
      get() {
        return (store as Record<string, unknown>)[key]
      },
      set(value) {
        ;(store as Record<string, unknown>)[key] = value
      },
      enumerable: true,
      configurable: true,
    })
  }

  return reactive(target)
}

/**
 * Backward-compatible facade that composes all 5 dweller sub-stores.
 * Consumers can continue using `useDwellerStore()` exactly as before.
 */
export const useDwellerStore = () => {
  const pinia = getActivePinia()
  if (cachedFacade && cachedPinia === pinia) {
    return cachedFacade
  }

  cachedPinia = pinia
  cachedFacade = buildDwellerFacade()
  return cachedFacade
}
