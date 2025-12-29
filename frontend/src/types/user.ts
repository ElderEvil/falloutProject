import type { components } from './api.generated'

// Re-export generated API types
export type User = components['schemas']['UserRead']
export type UserCreate = components['schemas']['UserCreate']
export type UserUpdate = components['schemas']['UserUpdate']
