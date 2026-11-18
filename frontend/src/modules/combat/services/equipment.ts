import { apiGet, apiPost } from '@/core/utils/api'
import type { Weapon, Outfit } from '../models/equipment'

// Weapon API calls
export async function fetchWeapons(vaultId: string): Promise<Weapon[]> {
  return apiGet<Weapon[]>('/api/v1/weapons/', { params: { vault_id: vaultId } })
}

export async function equipWeapon(dwellerId: string, weaponId: string): Promise<Weapon> {
  return apiPost<Weapon>(`/api/v1/weapons/${dwellerId}/equip/${weaponId}`, undefined, {
    skipErrorNotification: true,
  })
}

export async function unequipWeapon(weaponId: string): Promise<Weapon> {
  return apiPost<Weapon>(`/api/v1/weapons/${weaponId}/unequip/`, undefined, {
    skipErrorNotification: true,
  })
}

// Outfit API calls
export async function fetchOutfits(vaultId: string): Promise<Outfit[]> {
  return apiGet<Outfit[]>('/api/v1/outfits/', { params: { vault_id: vaultId } })
}

export async function equipOutfit(dwellerId: string, outfitId: string): Promise<Outfit> {
  return apiPost<Outfit>(`/api/v1/outfits/${dwellerId}/equip/${outfitId}`, undefined, {
    skipErrorNotification: true,
  })
}

export async function unequipOutfit(outfitId: string): Promise<Outfit> {
  return apiPost<Outfit>(`/api/v1/outfits/${outfitId}/unequip/`, undefined, {
    skipErrorNotification: true,
  })
}
