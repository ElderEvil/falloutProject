import { apiGet, apiPost } from '@/core/plugins/httpClient'
import type { Weapon, Outfit } from '../models/equipment'

function buildUrl(path: string, params?: Record<string, string>): string {
  if (!params) return path
  const searchParams = new URLSearchParams(params)
  return `${path}?${searchParams.toString()}`
}

// Weapon API calls
export async function fetchWeapons(_token: string, vaultId?: string): Promise<Weapon[]> {
  const url = buildUrl('/api/v1/weapons/', vaultId ? { vault_id: vaultId } : undefined)
  return apiGet<Weapon[]>(url)
}

export async function fetchWeapon(weaponId: string, _token: string): Promise<Weapon> {
  return apiGet<Weapon>(`/api/v1/weapons/${weaponId}`)
}

export async function equipWeapon(
  dwellerId: string,
  weaponId: string,
  _token: string
): Promise<Weapon> {
  return apiPost<Weapon>(`/api/v1/weapons/${dwellerId}/equip/${weaponId}`)
}

export async function unequipWeapon(
  _dwellerId: string,
  weaponId: string,
  _token: string
): Promise<Weapon> {
  return apiPost<Weapon>(`/api/v1/weapons/${weaponId}/unequip/`)
}

// Outfit API calls
export async function fetchOutfits(_token: string, vaultId?: string): Promise<Outfit[]> {
  const url = buildUrl('/api/v1/outfits/', vaultId ? { vault_id: vaultId } : undefined)
  return apiGet<Outfit[]>(url)
}

export async function fetchOutfit(outfitId: string, _token: string): Promise<Outfit> {
  return apiGet<Outfit>(`/api/v1/outfits/${outfitId}`)
}

export async function equipOutfit(
  dwellerId: string,
  outfitId: string,
  _token: string
): Promise<Outfit> {
  return apiPost<Outfit>(`/api/v1/outfits/${dwellerId}/equip/${outfitId}`)
}

export async function unequipOutfit(
  _dwellerId: string,
  outfitId: string,
  _token: string
): Promise<Outfit> {
  return apiPost<Outfit>(`/api/v1/outfits/${outfitId}/unequip/`)
}
