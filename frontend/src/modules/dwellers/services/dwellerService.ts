import axios from '@/core/plugins/axios'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

export interface DwellerQueryParams {
  status?: string
  ageGroup?: string
  search?: string
  sortBy?: string
  order?: 'asc' | 'desc'
  skip?: number
  limit?: number
}

export async function getDwellersByVault(
  vaultId: string,
  token: string,
  params?: DwellerQueryParams
): Promise<DwellerShort[]> {
  const query = new URLSearchParams()
  if (params?.status) query.append('status', params.status)
  if (params?.ageGroup) query.append('age_group', params.ageGroup)
  if (params?.search) query.append('search', params.search)
  if (params?.sortBy) query.append('sort_by', params.sortBy)
  if (params?.order) query.append('order', params.order)
  if (params?.skip !== undefined) query.append('skip', params.skip.toString())
  if (params?.limit !== undefined) query.append('limit', params.limit.toString())

  const queryString = query.toString()
  const url = `/api/v1/dwellers/vault/${vaultId}/${queryString ? `?${queryString}` : ''}`

  const response = await axios.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}
