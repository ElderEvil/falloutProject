/**
 * Central barrel file for all TypeScript types
 *
 * This provides a single import source for all types across the application,
 * reducing import boilerplate and improving consistency.
 *
 * Usage:
 * ```ts
 * import { Dweller, Room, Weapon } from '@/types'
 * ```
 */

// Re-export all API generated types
export type { components } from './api.generated'

// Re-export auth types
export type { Token, UserWithTokens, AuthError } from './auth'
export type { User } from './user'

// Re-export model types
export type {
  Dweller,
  DwellerFull,
  DwellerShort,
  DwellerCreate,
  DwellerUpdate,
  Special,
  VisualAttributes
} from '@/models/dweller'

export type {
  Room,
  RoomCreate,
  RoomUpdate
} from '@/models/room'

export type {
  Weapon,
  Outfit,
  ItemBase,
  WeaponType,
  WeaponSubtype,
  OutfitType,
  Gender,
  Rarity
} from '@/models/equipment'

export type {
  Relationship,
  RelationshipCreate,
  RelationshipUpdate
} from '@/models/relationship'

export type {
  Pregnancy
} from '@/models/pregnancy'

export type {
  Objective,
  ObjectiveCreate
} from '@/models/objective'

export type {
  Quest,
  QuestCreate
} from '@/models/quest'

export type {
  RadioStats
} from '@/models/radio'

export type {
  UserProfile,
  ProfileUpdate
} from '@/models/profile'

export type {
  ChatMessage
} from '@/models/chat'
