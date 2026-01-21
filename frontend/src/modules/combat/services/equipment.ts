import axios from '@/core/plugins/axios'
import type { Weapon, Outfit } from '../models/equipment'

// Weapon API calls
export async function fetchWeapons(token: string): Promise<Weapon[]> {
  const response = await axios.get('/api/v1/weapons/', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function fetchWeapon(weaponId: string, token: string): Promise<Weapon> {
  const response = await axios.get(`/api/v1/weapons/${weaponId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function equipWeapon(dwellerId: string, weaponId: string, token: string): Promise<Weapon> {
  const response = await axios.post(`/api/v1/weapons/${dwellerId}/equip/${weaponId}`, null, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function unequipWeapon(dwellerId: string, weaponId: string, token: string): Promise<Weapon> {
  const response = await axios.post(`/api/v1/weapons/${weaponId}/unequip/`, null, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

// Outfit API calls
export async function fetchOutfits(token: string): Promise<Outfit[]> {
  const response = await axios.get('/api/v1/outfits/', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function fetchOutfit(outfitId: string, token: string): Promise<Outfit> {
  const response = await axios.get(`/api/v1/outfits/${outfitId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function equipOutfit(dwellerId: string, outfitId: string, token: string): Promise<Outfit> {
  const response = await axios.post(`/api/v1/outfits/${dwellerId}/equip/${outfitId}`, null, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export async function unequipOutfit(dwellerId: string, outfitId: string, token: string): Promise<Outfit> {
  const response = await axios.post(`/api/v1/outfits/${outfitId}/unequip/`, null, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}
