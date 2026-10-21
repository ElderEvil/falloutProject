import { apiGet, apiPost } from '@/core/utils/api'
import type { Pet } from '../models/pet'

// Pet API calls
export async function fetchPets(vaultId: string): Promise<Pet[]> {
  return apiGet<Pet[]>('/api/v1/pets/', { params: { vault_id: vaultId } })
}

export async function fetchPet(petId: string): Promise<Pet> {
  return apiGet<Pet>(`/api/v1/pets/${petId}`)
}

export async function equipPet(dwellerId: string, petId: string): Promise<Pet> {
  return apiPost<Pet>(`/api/v1/pets/${dwellerId}/equip/${petId}`)
}

export async function unequipPet(petId: string): Promise<void> {
  await apiPost<void>(`/api/v1/pets/${petId}/unequip/`)
}
