import { number, z } from 'zod'
import { RoomGridSchema } from '@/validators/grid.validators'
import { RoomSchema } from '@/validators/rooms.validator'
import { VAULT_CONSTANTS } from '@/constants'

// Base resource schema for common validations
const ResourceSchema = z
  .object({
    type: z.string(),
    amount: z.number().min(0),
    capacity: z.number().min(0)
  })
  .refine((data) => data.amount <= data.capacity, {
    message: 'Current value cannot exceed maximum value',
    path: ['amount']
  })

// Main vault schema
const VaultSchema = z
  .object({
    id: z.string().uuid(),
    number: z.number().int().min(0).max(999),
    user_id: z.string().uuid(),

    // Resources
    bottle_caps: z.number().int().min(0),
    happiness: z.number().min(0).max(100),

    // Resources with max values
    power: z.number().min(0),
    power_max: z.number().min(0),
    food: z.number().min(0),
    food_max: z.number().min(0),
    water: z.number().min(0),
    water_max: z.number().min(0),

    // Population
    population_max: z
      .number()
      .int()
      .min(VAULT_CONSTANTS.MIN_VAULT_NUMBER)
      .max(VAULT_CONSTANTS.MAX_POPULATION),

    // Timestamps
    created_at: z.string().datetime(),
    updated_at: z.string().datetime(),

    // Structure
    grid: RoomGridSchema,
    rooms: RoomSchema
  })
  .refine((data) => data.power <= data.power_max, {
    message: 'Power cannot exceed maximum power',
    path: ['power']
  })
  .refine((data) => data.food <= data.food_max, {
    message: 'Food cannot exceed maximum food',
    path: ['food']
  })
  .refine((data) => data.water <= data.water_max, {
    message: 'Water cannot exceed maximum water',
    path: ['water']
  })

const VaultCreateSchema = z.object({
  number: number().int().min(VAULT_CONSTANTS.MIN_VAULT_NUMBER).max(VAULT_CONSTANTS.MAX_VAULT_NUMBER)
})

const VaultResourceUpdateSchema = z.object({
  power: z.number().min(0).optional(),
  food: z.number().min(0).optional(),
  water: z.number().min(0).optional(),
  bottle_caps: z.number().int().min(0).optional(),
  happiness: z.number().min(0).max(100).optional()
})

export { VaultSchema, VaultCreateSchema, VaultResourceUpdateSchema, ResourceSchema }
