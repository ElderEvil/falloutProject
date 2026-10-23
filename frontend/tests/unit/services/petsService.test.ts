import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApiClientMock } from '../helpers/mocks'
import { apiGet, apiPost } from '@/core/utils/api'

vi.mock('@/core/utils/api', () => createApiClientMock())

import { equipPet, fetchPet, fetchPets, unequipPet } from '@/modules/pets/services/pets'

describe('petsService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetchPets requests the vault list through the shared boundary', async () => {
    const pets = [{ id: 'pet-1' }]
    vi.mocked(apiGet).mockResolvedValueOnce(pets)

    await expect(fetchPets('vault-1')).resolves.toEqual(pets)
    expect(apiGet).toHaveBeenCalledWith('/api/v1/pets/', { params: { vault_id: 'vault-1' } })
  })

  it('fetchPet requests a single pet', async () => {
    const pet = { id: 'pet-1' }
    vi.mocked(apiGet).mockResolvedValueOnce(pet)

    await expect(fetchPet('pet-1')).resolves.toEqual(pet)
    expect(apiGet).toHaveBeenCalledWith('/api/v1/pets/pet-1')
  })

  it('equipPet posts to the equip endpoint', async () => {
    const pet = { id: 'pet-1', dweller_id: 'dweller-1' }
    vi.mocked(apiPost).mockResolvedValueOnce(pet)

    await expect(equipPet('dweller-1', 'pet-1')).resolves.toEqual(pet)
    expect(apiPost).toHaveBeenCalledWith('/api/v1/pets/dweller-1/equip/pet-1')
  })

  it('unequipPet posts to the unequip endpoint', async () => {
    vi.mocked(apiPost).mockResolvedValueOnce(undefined)

    await expect(unequipPet('pet-1')).resolves.toBeUndefined()
    expect(apiPost).toHaveBeenCalledWith('/api/v1/pets/pet-1/unequip/')
  })

  it('propagates boundary errors unchanged', async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error('Network error'))

    await expect(fetchPets('vault-1')).rejects.toThrow('Network error')
  })
})
