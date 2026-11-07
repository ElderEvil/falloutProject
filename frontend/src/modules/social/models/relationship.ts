/**
 * TypeScript models for dweller relationships
 */

export type RelationshipType =
  | 'acquaintance'
  | 'friend'
  | 'romantic'
  | 'partner'
  | 'MARRIED'
  | 'rival'
  | 'ex'

export const PARTNER_LINKED_RELATIONSHIP_TYPES: readonly RelationshipType[] = ['partner', 'MARRIED']

export const COMMITTED_RELATIONSHIP_TYPES: readonly RelationshipType[] = [
  ...PARTNER_LINKED_RELATIONSHIP_TYPES,
  'romantic',
]

export type RelationshipVariant =
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'default'
  | 'primary'
  | 'secondary'
  | 'outline'

export const RELATIONSHIP_TYPE_VARIANT: Record<RelationshipType, RelationshipVariant> = {
  acquaintance: 'outline',
  friend: 'success',
  romantic: 'warning',
  partner: 'info',
  MARRIED: 'primary',
  rival: 'danger',
  ex: 'default',
}

export const RELATIONSHIP_TYPE_LABEL: Record<RelationshipType, string> = {
  acquaintance: 'Acquaintance',
  friend: 'Friend',
  romantic: 'Romantic',
  partner: 'Partner',
  MARRIED: 'Married',
  rival: 'Rival',
  ex: 'Ex',
}

export function isRelationshipType(
  type: RelationshipType,
  types: readonly RelationshipType[]
): boolean {
  return types.includes(type)
}

export interface Relationship {
  id: string
  dweller_1_id: string
  dweller_2_id: string
  relationship_type: RelationshipType
  affinity: number // -100-100; negative is rivalry
  bond_change_per_tick?: number
  bond_tick_seconds?: number
  conception_potential?: 'possible' | 'race' | 'age' | 'gender'
  same_race?: boolean
  average_charisma?: number
  can_make_partners?: boolean
  discomfort_severity?: 'mild' | 'moderate' | 'strong'
  discomfort_source?: 'feral' | 'mutant' | 'behemoth' | 'synth_gen_1' | 'synth_gen_2'
  created_at?: string
  updated_at?: string
}

export interface CompatibilityScore {
  dweller_1_id: string
  dweller_2_id: string
  score: number // 0.0 - 1.0
  special_score: number
  happiness_score: number
  level_score: number
  proximity_score: number
}

export interface RelationshipCreate {
  dweller_1_id: string
  dweller_2_id: string
}

export interface RelationshipUpdate {
  relationship_type?: RelationshipType
  affinity?: number
}
