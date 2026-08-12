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

export interface DwellerStoreSlices {
  filter: ReturnType<typeof useDwellerFilterStore>
  generation: ReturnType<typeof useDwellerGenerationStore>
  management: ReturnType<typeof useDwellerManagementStore>
  medical: ReturnType<typeof useDwellerMedicalStore>
  death: ReturnType<typeof useDwellerDeathStore>
}

/**
 * Groups the dweller domain's independent Pinia stores without flattening their
 * state. Consumers retain each slice's native Pinia API (`$id`, `$patch`, and
 * `storeToRefs`) and loading state can no longer collide across concerns.
 */
export const useDwellerStore = (): DwellerStoreSlices => ({
  filter: useDwellerFilterStore(),
  generation: useDwellerGenerationStore(),
  management: useDwellerManagementStore(),
  medical: useDwellerMedicalStore(),
  death: useDwellerDeathStore(),
})
