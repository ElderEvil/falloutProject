import axios from '@/core/plugins/axios'
import type { Pet } from '../models/pet'

// Pet API calls
export async function fetchPets(token: string, vaultId: string): Promise<Pet[]> {
  const params = { vault_id: vaultId }
  const response = await axios.get('/api/v1/pets/', {
    params,
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function fetchPet(petId: string, token: string): Promise<Pet> {
  const response = await axios.get(`/api/v1/pets/${petId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function equipPet(dwellerId: string, petId: string, token: string): Promise<Pet> {
  const response = await axios.post(`/api/v1/pets/${dwellerId}/equip/${petId}`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function unequipPet(petId: string, token: string): Promise<void> {
  await axios.post(`/api/v1/pets/${petId}/unequip/`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
}
