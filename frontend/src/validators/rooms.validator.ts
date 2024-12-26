import { z } from 'zod'
import { RoomCategory, SpecialAbility, ROOM_CONSTANTS } from '@/constants'

// Enums for room categories and abilities
const RoomCategoryEnum = z.enum(Object.values(RoomCategory) as [string, ...string[]])
const RoomAbilityEnum = z.enum(Object.values(SpecialAbility) as [string, ...string[]]).nullable()

const RoomShortInfoSchema = z.object({
  name: z.string().min(ROOM_CONSTANTS.MIN_NAME_LENGTH),
  category: RoomCategoryEnum,
  ability: RoomAbilityEnum
})

// Base schema for room
const RoomSchema = z.object({
  // General info
  id: z.string().uuid(),
  name: z.string().min(ROOM_CONSTANTS.MIN_NAME_LENGTH),
  category: RoomCategoryEnum,
  ability: RoomAbilityEnum,

  // Capacity and Requirements
  population_required: z.number().int().min(ROOM_CONSTANTS.MIN_POPULATION).nullable(),
  capacity: z.number().int().min(0).nullable(),
  output: z.number().min(0).nullable(),

  // Size properties
  size_min: z.number().int().min(ROOM_CONSTANTS.MIN_SIZE),
  size_max: z.number().int().min(ROOM_CONSTANTS.MIN_SIZE),
  size: z.number().int().min(ROOM_CONSTANTS.MIN_SIZE).max(ROOM_CONSTANTS.MAX_SIZE),

  // Cost properties
  base_cost: z.number().int().min(0),
  incremental_cost: z.number().int().min(0),
  t2_upgrade_cost: z.number().int().min(0).optional(),
  t3_upgrade_cost: z.number().int().min(0).optional(),

  // Location properties
  coordinate_x: z.number().int(),
  coordinate_y: z.number().int(),
  tier: z.number().int().min(ROOM_CONSTANTS.MIN_TIER).max(ROOM_CONSTANTS.MAX_TIER),
  image_url: z.string().url().nullable(),

  // Timestamps
  created_at: z.string().datetime(),
  updated_at: z.string().datetime()
})

// Schema for creating a new room
const RoomCreateSchema = RoomSchema.omit({
  id: true,
  created_at: true,
  updated_at: true
})

// Schema for updating room
const RoomUpdateSchema = RoomSchema.partial().pick({
  size: true,
  coordinate_x: true,
  coordinate_y: true,
  tier: true,
  output: true,
  capacity: true,
  population_required: true
})

// Schema for room upgrade
const RoomUpgradeSchema = z.object({
  tier: z.number().int().min(1).max(3),
  cost: z.number().int().min(0)
})

// Helper function to calculate upgrade cost
const calculateUpgradeCost = (room: z.infer<typeof RoomSchema>) => {
  if (room.tier === 1) return room.t2_upgrade_cost
  if (room.tier === 2) return room.t3_upgrade_cost
  return null
}

export {
  RoomShortInfoSchema,
  RoomSchema,
  RoomCreateSchema,
  RoomUpdateSchema,
  RoomUpgradeSchema,
  RoomCategoryEnum,
  RoomAbilityEnum,
  calculateUpgradeCost
}
