import axios from '@/core/plugins/axios'

export interface LineageMember {
  id: string
  first_name: string
  last_name: string | null
  generation: number
  is_dead: boolean
  age_group: 'child' | 'teen' | 'adult'
  // Partner context — only populated for the `partners` array.
  relationship_type?: 'acquaintance' | 'friend' | 'romantic' | 'partner' | 'MARRIED' | 'ex'
  affinity?: number
}

export interface LineageResponse {
  dweller_id: string
  generation: number
  parents: LineageMember[]
  children: LineageMember[]
  siblings: LineageMember[]
  partners: LineageMember[]
}

/**
 * Fetch the computed family lineage for a dweller (parents, children, siblings,
 * partners, and generation depth). Backed by GET /api/v1/dwellers/{id}/lineage.
 */
export async function getLineage(dwellerId: string): Promise<LineageResponse> {
  const response = await axios.get<LineageResponse>(`/api/v1/dwellers/${dwellerId}/lineage`)
  return response.data
}
