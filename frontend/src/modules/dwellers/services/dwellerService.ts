import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

export type IdentityOptions = components['schemas']['DwellerIdentityOptions']
export type AppearanceOptions = components['schemas']['DwellerAppearanceOptions']
export type FeatureFlags = components['schemas']['FeaturesResponse']

export interface DwellerQueryParams {
  focus?: components['schemas']['DwellerRosterFocus']
  status?: string
  ageGroup?: string
  gender?: string
  rarity?: string
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
  params: DwellerQueryParams = {}
): Promise<DwellerShort[]> {
  const query = new URLSearchParams()
  if (params.focus) query.append('focus', params.focus)
  if (params.status) query.append('status', params.status)
  if (params.ageGroup) query.append('age_group', params.ageGroup)
  if (params.gender) query.append('gender', params.gender)
  if (params.rarity) query.append('rarity', params.rarity)
  if (params.race) query.append('race', params.race)
  if (params.faction) query.append('faction', params.faction)
  if (params.search) query.append('search', params.search)
  if (params.sortBy) query.append('sort_by', params.sortBy)
  if (params.order) query.append('order', params.order)
  if (params.skip !== undefined) query.append('skip', params.skip.toString())
  if (params.limit !== undefined) query.append('limit', params.limit.toString())

  const queryString = query.toString()
  const url = `/api/v1/dwellers/vault/${vaultId}/${queryString ? `?${queryString}` : ''}`
  return apiGet<DwellerShort[]>(url, { signal: params.signal })
}

export async function getDweller(id: string): Promise<Dweller> {
  return apiGet<Dweller>(`/api/v1/dwellers/${id}`)
}

export async function appendBioAddendum(dwellerId: string, text: string): Promise<Dweller> {
  return apiPost<Dweller>(`/api/v1/dwellers/${dwellerId}/bio/addendum/`, { text })
}

export async function getIdentityOptions(): Promise<IdentityOptions> {
  return apiGet<IdentityOptions>('/api/v1/dwellers/identity-options')
}

export async function getAppearanceOptions(): Promise<AppearanceOptions> {
  return apiGet<AppearanceOptions>('/api/v1/dwellers/appearance-options')
}

export async function getFeatureFlags(): Promise<FeatureFlags> {
  return apiGet<FeatureFlags>('/api/v1/system/features')
}
