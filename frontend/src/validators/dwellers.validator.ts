import { z } from 'zod'

import { RarityEnum } from './common.validators'

const GenderEnum = z.enum(['male', 'female'])

const specialAttribute = z.number().int().min(1).max(10)

const VisualAttributesSchema = z.object({
  age: z.enum(['child', 'adult', 'elderly']),
  build: z.enum(['slim', 'average', 'muscular', 'heavy']),
  height: z.enum(['short', 'average', 'tall']),
  eye_color: z.string().min(1),
  skin_tone: z.string().min(1),
  appearance: z.string().min(1),
  hair_color: z.string().min(1),
  hair_style: z.string().min(1),
  clothing_style: z.string().min(1)
})

const DwellerBaseSchema = z.object({
  id: z.string().uuid(),
  first_name: z.string().min(2),
  last_name: z.string().optional(),
  level: z.number().int().positive(),
  experience: z.number().int().min(0),
  health: z.number().min(0),
  max_health: z.number().min(0),
  radiation: z.number().min(0),
  happiness: z.number().min(0).max(100),
  thumbnail_url: z.string().url(),

  // Additional
  room_id: z.string().uuid().optional()
})

const DwellerShortSchema = DwellerBaseSchema.extend({
  gender: GenderEnum,
  rarity: RarityEnum
})

const SpecialStatsSchema = z.object({
  strength: specialAttribute,
  perception: specialAttribute,
  endurance: specialAttribute,
  charisma: specialAttribute,
  intelligence: specialAttribute,
  agility: specialAttribute,
  luck: specialAttribute
})

const DwellerFullSchema = DwellerShortSchema.extend({
  is_adult: z.boolean(),
  bio: z.string().min(1),
  visual_attributes: VisualAttributesSchema,
  image_url: z.string().url(),
  ...SpecialStatsSchema.shape,
  stimpack: z.number().int().min(0),
  radaway: z.number().int().min(0),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime()
})

export {
  DwellerBaseSchema,
  DwellerShortSchema,
  DwellerFullSchema,
  SpecialStatsSchema,
  VisualAttributesSchema,
  GenderEnum
}
