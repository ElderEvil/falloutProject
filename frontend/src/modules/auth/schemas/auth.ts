import { z } from 'zod'

/**
 * Login form validation schema
 * Using Zod v4 best practices: top-level validators and unified error parameter
 */
export const loginSchema = z.object({
  username: z
    .string({
      error: 'Username must be a string',
    })
    .min(3, { error: 'Username must be at least 3 characters' })
    .max(50, { error: 'Username must be less than 50 characters' })
    .regex(/^[a-zA-Z0-9_-]+$/, {
      error: 'Username can only contain letters, numbers, underscores, and hyphens',
    }),
  password: z
    .string({
      error: 'Password is required',
    })
    .min(1, { error: 'Password is required' }),
})

export type LoginFormData = z.infer<typeof loginSchema>

/**
 * Register form validation schema
 * Using Zod v4 best practices: top-level validators and unified error parameter
 */
export const registerSchema = z.object({
  username: z
    .string({
      error: 'Username must be a string',
    })
    .min(3, { error: 'Username must be at least 3 characters' })
    .max(50, { error: 'Username must be less than 50 characters' })
    .regex(/^[a-zA-Z0-9_-]+$/, {
      error: 'Username can only contain letters, numbers, underscores, and hyphens',
    }),
  email: z.email({ error: 'Invalid email address' }),
  password: z
    .string({
      error: 'Password must be a string',
    })
    .min(8, { error: 'Password must be at least 8 characters' })
    .regex(/[A-Z]/, { error: 'Password must contain at least one uppercase letter' })
    .regex(/[a-z]/, { error: 'Password must contain at least one lowercase letter' })
    .regex(/[0-9]/, { error: 'Password must contain at least one number' }),
})

export type RegisterFormData = z.infer<typeof registerSchema>
