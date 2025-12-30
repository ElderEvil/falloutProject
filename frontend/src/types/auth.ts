import type { components } from './api.generated'

// Re-export generated API types
export type Token = components['schemas']['Token']
export type UserWithTokens = components['schemas']['UserWithTokens']

// Form types are now in schemas/auth.ts with Zod validation
// Import from there for form validation

export class AuthError extends Error {
  constructor(
    message: string,
    public code?: number
  ) {
    super(message)
    this.name = 'AuthError'
  }
}
