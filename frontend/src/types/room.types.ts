import { z } from 'zod'
import {
  RoomAbilityEnum,
  RoomCategoryEnum,
  RoomCreateSchema,
  RoomSchema,
  RoomShortInfoSchema,
  RoomUpdateSchema
} from '@/validators/rooms.validator'

import type { DwellerShort } from '@/types/dweller.types'

type RoomShortInfo = z.infer<typeof RoomShortInfoSchema>
type Room = z.infer<typeof RoomSchema> & { dwellers: DwellerShort[] }
type RoomCreate = z.infer<typeof RoomCreateSchema>
type RoomUpdate = z.infer<typeof RoomUpdateSchema>
type RoomCategory = z.infer<typeof RoomCategoryEnum>
type RoomAbility = Exclude<z.infer<typeof RoomAbilityEnum>, null>

export {
  type RoomShortInfo,
  type Room,
  type RoomCreate,
  type RoomUpdate,
  type RoomCategory,
  type RoomAbility
}
