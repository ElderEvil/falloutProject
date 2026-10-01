import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePetsStore } from '@/modules/pets/stores/pets'
import * as petsService from '@/modules/pets/services/pets'
import type { Pet } from '@/modules/pets/models/pet'

vi.mock('@/modules/pets/services/pets')

const toastMock = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => toastMock,
}))

const neutralEffect = {
  strength: 0,
  perception: 0,
  endurance: 0,
  charisma: 0,
  intelligence: 0,
  agility: 0,
  luck: 0,
  max_health: 0,
  damage_pct: 0,
  incident_response_pct: 0,
  radiation_resist_pct: 0,
  happiness: 0,
  caps_pct: 0,
  xp_pct: 0,
  training_speed_pct: 0,
}

function makePet(overrides: Partial<Pet> = {}): Pet {
  return {
    id: 'pet-1',
    name: 'Dogmeat',
    rarity: 'rare',
    value: 100,
    image_url: null,
    dweller_id: null,
    storage_id: 'storage-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    effect: neutralEffect,
    ...overrides,
  }
}

describe('Pets Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchPets calls the service and stores the list', async () => {
    const store = usePetsStore()
    const pets = [makePet(), makePet({ id: 'pet-2', name: 'CX404' })]
    vi.mocked(petsService.fetchPets).mockResolvedValueOnce(pets)

    await store.fetchPets('token', 'vault-1')

    expect(petsService.fetchPets).toHaveBeenCalledWith('token', 'vault-1')
    expect(store.pets).toEqual(pets)
    expect(store.error).toBeNull()
  })

  it('fetchPets failure sets the error and toasts without touching state', async () => {
    const store = usePetsStore()
    store.pets = [makePet()]
    vi.mocked(petsService.fetchPets).mockRejectedValueOnce(new Error('Network error'))

    await store.fetchPets('token', 'vault-1')

    expect(store.error).toBe('Failed to load pets')
    expect(toastMock.error).toHaveBeenCalledWith('Failed to load pets')
    expect(store.pets).toHaveLength(1)
  })

  it('equipPet calls the service and updates the pet in state', async () => {
    const store = usePetsStore()
    store.pets = [makePet()]
    const equipped = makePet({ dweller_id: 'dweller-1' })
    vi.mocked(petsService.equipPet).mockResolvedValueOnce(equipped)

    const result = await store.equipPet('dweller-1', 'pet-1', 'token')

    expect(petsService.equipPet).toHaveBeenCalledWith('dweller-1', 'pet-1', 'token')
    expect(result).toEqual(equipped)
    expect(store.pets[0]).toEqual(equipped)
    expect(toastMock.success).toHaveBeenCalledWith('Pet equipped successfully!')
  })

  it('equipPet failure goes through handleStoreError and returns null', async () => {
    const store = usePetsStore()
    store.pets = [makePet()]
    vi.mocked(petsService.equipPet).mockRejectedValueOnce(new Error('Equip failed'))

    const result = await store.equipPet('dweller-1', 'pet-1', 'token')

    expect(result).toBeNull()
    expect(toastMock.error).toHaveBeenCalledWith('Failed to equip pet: Equip failed')
    expect(store.pets[0].dweller_id).toBeNull()
  })

  it('unequipPet calls the service and updates the pet in state', async () => {
    const store = usePetsStore()
    store.pets = [makePet({ dweller_id: 'dweller-1' })]
    const unequipped = makePet()
    vi.mocked(petsService.unequipPet).mockResolvedValueOnce(unequipped)

    const result = await store.unequipPet('dweller-1', 'pet-1', 'token')

    expect(petsService.unequipPet).toHaveBeenCalledWith('pet-1', 'token')
    expect(result).toEqual(unequipped)
    expect(store.pets[0]).toEqual(unequipped)
    expect(toastMock.success).toHaveBeenCalledWith('Pet unequipped successfully!')
  })

  it('unequipPet failure goes through handleStoreError and returns null', async () => {
    const store = usePetsStore()
    vi.mocked(petsService.unequipPet).mockRejectedValueOnce(new Error('Unequip failed'))

    const result = await store.unequipPet('dweller-1', 'pet-1', 'token')

    expect(result).toBeNull()
    expect(toastMock.error).toHaveBeenCalledWith('Failed to unequip pet: Unequip failed')
  })

  it('getEquippedPet returns the pet equipped to a dweller', () => {
    const store = usePetsStore()
    store.pets = [makePet(), makePet({ id: 'pet-2', dweller_id: 'dweller-1' })]

    expect(store.getEquippedPet('dweller-1')?.id).toBe('pet-2')
    expect(store.getEquippedPet('missing')).toBeNull()
  })

  it('getAvailablePets returns only unequipped pets', () => {
    const store = usePetsStore()
    store.pets = [makePet(), makePet({ id: 'pet-2', dweller_id: 'dweller-1' })]

    expect(store.getAvailablePets().map((p) => p.id)).toEqual(['pet-1'])
  })
})
