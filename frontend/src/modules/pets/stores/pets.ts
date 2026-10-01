import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Pet } from '../models/pet'
import * as petsService from '../services/pets'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useAsyncAction } from '@/core/composables/useAsyncAction'

export const usePetsStore = defineStore('pets', () => {
  const toast = useToast()

  // State
  const pets = ref<Pet[]>([])
  const error = ref<string | null>(null)
  const { run: runFetchPets, isLoading: isPetsLoading } = useAsyncAction(
    (token: string, vaultId: string) => petsService.fetchPets(token, vaultId),
    { context: 'Failed to fetch pets', showToast: false }
  )
  const isLoading = computed(() => isPetsLoading.value)

  // Actions
  async function fetchPets(token: string, vaultId: string): Promise<void> {
    error.value = null
    const result = await runFetchPets(token, vaultId)
    if (result) {
      pets.value = result
    } else {
      error.value = 'Failed to load pets'
      toast.error('Failed to load pets')
    }
  }

  async function equipPet(dwellerId: string, petId: string, token: string): Promise<Pet | null> {
    try {
      const pet = await petsService.equipPet(dwellerId, petId, token)

      // Update local state: unequip from previous dweller, equip to new dweller
      const petIndex = pets.value.findIndex((p) => p.id === petId)
      if (petIndex !== -1) {
        pets.value[petIndex] = pet
      }

      toast.success('Pet equipped successfully!')
      return pet
    } catch (err) {
      handleStoreError(err, 'Failed to equip pet')
      toast.error('Failed to equip pet')
      return null
    }
  }

  async function unequipPet(dwellerId: string, petId: string, token: string): Promise<Pet | null> {
    try {
      await petsService.unequipPet(petId, token)

      // The API returns no body on unequip, so reflect the change locally.
      const petIndex = pets.value.findIndex((p) => p.id === petId)
      let updated: Pet | null = null
      if (petIndex !== -1) {
        updated = { ...pets.value[petIndex], dweller_id: null }
        pets.value[petIndex] = updated
      }

      toast.success('Pet unequipped successfully!')
      return updated
    } catch (err) {
      handleStoreError(err, 'Failed to unequip pet')
      toast.error('Failed to unequip pet')
      return null
    }
  }

  // Getters
  function getEquippedPet(dwellerId: string): Pet | null {
    return pets.value.find((p) => p && p.dweller_id === dwellerId) || null
  }

  function getAvailablePets(): Pet[] {
    return pets.value.filter((p) => p && !p.dweller_id)
  }

  return {
    // State
    pets,
    isLoading,
    error,
    // Actions
    fetchPets,
    equipPet,
    unequipPet,
    // Getters
    getEquippedPet,
    getAvailablePets,
  }
})
