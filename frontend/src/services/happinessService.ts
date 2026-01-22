// Re-export from the dwellers module for backward compatibility
// This file will be removed in a future cleanup when all imports are updated

export {
  happinessService,
  type HappinessModifiers,
  type HappinessModifier as Modifier
} from '@/modules/dwellers/services/happinessService'
