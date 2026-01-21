/**
 * TypeScript models for dweller relationships
 */

export type RelationshipType = 'acquaintance' | 'friend' | 'romantic' | 'partner' | 'ex'

export interface Relationship {
  id: string
  dweller_1_id: string
  dweller_2_id: string
  relationship_type: RelationshipType
  affinity: number // 0-100
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
