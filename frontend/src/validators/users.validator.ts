import { z } from 'zod'

// Base schema with common validations
const userBaseSchema = z.object({
  username: z
    .string()
    .min(3, 'Username must be at least 3 characters')
    .max(50, 'Username cannot exceed 50 characters')
    .regex(
      /^[a-zA-Z0-9_-]+$/,
      'Username can only contain letters, numbers, underscores, and hyphens'
    ),

  email: z
    .string()
    .email('Invalid email format')
    .min(5, 'Email must be at least 5 characters')
    .max(255, 'Email cannot exceed 255 characters')
})

// Schema for user creation/registration
const userCreateSchema = userBaseSchema
  .extend({
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .max(100, 'Password cannot exceed 100 characters')
      .regex(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
        'Password must contain at least one uppercase letter, one lowercase letter, and one number'
      ),

    confirmPassword: z.string()
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword']
  })

// Schema for reading user data (no sensitive info)
const userReadSchema = userBaseSchema.extend({
  id: z.string().uuid(),
  createdAt: z.date(),
  updatedAt: z.date()
})

// Schema for updating user data
const userUpdateSchema = userBaseSchema
  .partial()
  .extend({
    currentPassword: z.string().optional(),
    newPassword: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .max(100, 'Password cannot exceed 100 characters')
      .regex(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
        'Password must contain at least one uppercase letter, one lowercase letter, and one number'
      )
      .optional(),
    confirmNewPassword: z.string().optional()
  })
  .refine(
    (data) => {
      if (data.newPassword) {
        return data.newPassword === data.confirmNewPassword
      }
      return true
    },
    {
      message: "New passwords don't match",
      path: ['confirmNewPassword']
    }
  )
  .refine(
    (data) => {
      if (data.newPassword) {
        return !!data.currentPassword
      }
      return true
    },
    {
      message: 'Current password is required to set new password',
      path: ['currentPassword']
    }
  )

// Type inference
type UserCreate = z.infer<typeof userCreateSchema>
type UserRead = z.infer<typeof userReadSchema>
type UserUpdate = z.infer<typeof userUpdateSchema>

export {
  userBaseSchema,
  userCreateSchema,
  userReadSchema,
  userUpdateSchema,
  type UserCreate,
  type UserRead,
  type UserUpdate
}
