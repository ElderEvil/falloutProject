/**
 * Central barrel file for all TypeScript types
 *
 * This provides a single import source for all types across the application,
 * reducing import boilerplate and improving consistency.
 *
 * Usage:
 * ```ts
 * import type { components } from '@/core/types'
 * import type { Dweller } from '@/models/dweller'  // Use module-specific imports
 * ```
 *
 * Note: Module-specific types are now in their respective modules:
 * - Auth types: @/modules/auth/types
 * - Vault types: @/modules/vault/types
 * - Radio types: @/modules/radio/models
 * - Profile types: @/modules/profile/models
 * - Chat types: @/modules/chat/models
 */

// Re-export all API generated types
export type { components } from './api.generated'

// Utility types
export * from './utils'

// Note: For model types, import directly from @/models/* or respective modules
