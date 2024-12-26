import { z } from 'zod'
import {
  DwellerFullSchema,
  DwellerShortSchema,
  SpecialStatsSchema,
  VisualAttributesSchema
} from '@/validators/dwellers.validator'

type DwellerShort = z.infer<typeof DwellerShortSchema>
type DwellerFull = z.infer<typeof DwellerFullSchema>
type SpecialStats = z.infer<typeof SpecialStatsSchema>
type VisualAttributes = z.infer<typeof VisualAttributesSchema>

export { type DwellerShort, type DwellerFull, type SpecialStats, type VisualAttributes }
