import type { components } from '@/core/types/api.generated'
import { apiGet } from '@/core/utils/api'

export type LineageMember = components['schemas']['LineageMember']
export type LineageResponse = components['schemas']['LineageResponse']

/**
 * Fetch the computed family lineage for a dweller (parents, children, siblings,
 * partners, and generation depth). Backed by GET /api/v1/dwellers/{id}/lineage.
 */
export async function getLineage(dwellerId: string): Promise<LineageResponse> {
  return apiGet<LineageResponse>(`/api/v1/dwellers/${dwellerId}/lineage`)
}
