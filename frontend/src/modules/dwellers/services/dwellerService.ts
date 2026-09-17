import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

export type IdentityOptions = components['schemas']['DwellerIdentityOptions']
export type FeatureFlags = components['schemas']['FeaturesResponse']

export interface DwellerQueryParams {
  status?: string
  ageGroup?: string
  race?: string
  faction?: string
  search?: string
  sortBy?: string
  order?: 'asc' | 'desc'
  skip?: number
  limit?: number
  signal?: AbortSignal
}

export async function getDwellersByVault(
  vaultId: string,
  token: string,
  params?: DwellerQueryParams
): Promise<DwellerShort[]> {
  const query = new URLSearchParams()
  if (params?.status) query.append('status', params.status)
  if (params?.ageGroup) query.append('age_group', params.ageGroup)
  if (params?.race) query.append('race', params.race)
  if (params?.faction) query.append('faction', params.faction)
  if (params?.search) query.append('search', params.search)
  if (params?.sortBy) query.append('sort_by', params.sortBy)
  if (params?.order) query.append('order', params.order)
  if (params?.skip !== undefined) query.append('skip', params.skip.toString())
  if (params?.limit !== undefined) query.append('limit', params.limit.toString())

  const queryString = query.toString()
  const url = `/api/v1/dwellers/vault/${vaultId}/${queryString ? `?${queryString}` : ''}`

  const response = await axios.get(url, {
    headers: { Authorization: `Bearer ${token}` },
    signal: params?.signal,
  })
  return response.data
}

export async function getDweller(id: string, token: string): Promise<Dweller> {
  const response = await axios.get<Dweller>(`/api/v1/dwellers/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function appendBioAddendum(dwellerId: string, text: string, token: string): Promise<Dweller> {
  const response = await axios.post<Dweller>(
    `/api/v1/dwellers/${dwellerId}/bio/addendum/`,
    { text },
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

export async function getIdentityOptions(token: string): Promise<IdentityOptions> {
  const response = await axios.get<IdentityOptions>('/api/v1/dwellers/identity-options', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function getFeatureFlags(): Promise<FeatureFlags> {
  const response = await axios.get<FeatureFlags>('/api/v1/system/features')
  return response.data
}
