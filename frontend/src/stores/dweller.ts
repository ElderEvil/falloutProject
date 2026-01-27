// Re-export from the dwellers module for backward compatibility
// This file will be removed in a future cleanup when all imports are updated

export {
  useDwellerStore,
  type DwellerStatus,
  type DwellerWithStatus,
  type DwellerSortBy,
  type SortDirection,
} from '@/modules/dwellers/stores/dweller'

// Re-export Dweller types for components that import from @/stores/dweller
// DwellerShort is used in the store's dwellers array
export type { DwellerShort as Dweller, DwellerFull } from '@/modules/dwellers/models/dweller'
