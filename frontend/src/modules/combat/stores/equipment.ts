import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Weapon, Outfit } from '../models/equipment'
import * as equipmentService from '../services/equipment'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

export const useEquipmentStore = defineStore('equipment', () => {
  const toast = useToast()

  // State
  const weapons = ref<Weapon[]>([])
  const outfits = ref<Outfit[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Actions
  async function fetchWeapons(token: string, vaultId?: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      weapons.value = await equipmentService.fetchWeapons(token, vaultId)
    } catch (err) {
      handleStoreError(err, 'Failed to fetch weapons')
      error.value = 'Failed to load weapons'
      toast.error('Failed to load weapons')
    } finally {
      isLoading.value = false
    }
  }

  async function fetchOutfits(token: string, vaultId?: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      outfits.value = await equipmentService.fetchOutfits(token, vaultId)
    } catch (err) {
      handleStoreError(err, 'Failed to fetch outfits')
      error.value = 'Failed to load outfits'
      toast.error('Failed to load outfits')
    } finally {
      isLoading.value = false
    }
  }

  async function equipWeapon(
    dwellerId: string,
    weaponId: string,
    token: string
  ): Promise<Weapon | null> {
    try {
      const weapon = await equipmentService.equipWeapon(dwellerId, weaponId, token)

      // Update local state: unequip from previous dweller, equip to new dweller
      const weaponIndex = weapons.value.findIndex((w) => w.id === weaponId)
      if (weaponIndex !== -1) {
        weapons.value[weaponIndex] = weapon
      }

      toast.success('Weapon equipped successfully!')
      return weapon
    } catch (err) {
      handleStoreError(err, 'Failed to equip weapon')
      toast.error('Failed to equip weapon')
      return null
    }
  }

  async function unequipWeapon(
    dwellerId: string,
    weaponId: string,
    token: string
  ): Promise<Weapon | null> {
    try {
      const weapon = await equipmentService.unequipWeapon(dwellerId, weaponId, token)

      // Update local state
      const weaponIndex = weapons.value.findIndex((w) => w.id === weaponId)
      if (weaponIndex !== -1) {
        weapons.value[weaponIndex] = weapon
      }

      toast.success('Weapon unequipped successfully!')
      return weapon
    } catch (err) {
      handleStoreError(err, 'Failed to unequip weapon')
      toast.error('Failed to unequip weapon')
      return null
    }
  }

  async function equipOutfit(
    dwellerId: string,
    outfitId: string,
    token: string
  ): Promise<Outfit | null> {
    try {
      const outfit = await equipmentService.equipOutfit(dwellerId, outfitId, token)

      // Update local state: unequip from previous dweller, equip to new dweller
      const outfitIndex = outfits.value.findIndex((o) => o.id === outfitId)
      if (outfitIndex !== -1) {
        outfits.value[outfitIndex] = outfit
      }

      toast.success('Outfit equipped successfully!')
      return outfit
    } catch (err) {
      handleStoreError(err, 'Failed to equip outfit')
      toast.error('Failed to equip outfit')
      return null
    }
  }

  async function unequipOutfit(
    dwellerId: string,
    outfitId: string,
    token: string
  ): Promise<Outfit | null> {
    try {
      const outfit = await equipmentService.unequipOutfit(dwellerId, outfitId, token)

      // Update local state
      const outfitIndex = outfits.value.findIndex((o) => o.id === outfitId)
      if (outfitIndex !== -1) {
        outfits.value[outfitIndex] = outfit
      }

      toast.success('Outfit unequipped successfully!')
      return outfit
    } catch (err) {
      handleStoreError(err, 'Failed to unequip outfit')
      toast.error('Failed to unequip outfit')
      return null
    }
  }

  // Getters
  function getEquippedWeapon(dwellerId: string): Weapon | null {
    return weapons.value.find((w) => w && w.dweller_id === dwellerId) || null
  }

  function getEquippedOutfit(dwellerId: string): Outfit | null {
    return outfits.value.find((o) => o && o.dweller_id === dwellerId) || null
  }

  function getAvailableWeapons(): Weapon[] {
    return weapons.value.filter((w) => w && !w.dweller_id)
  }

  function getAvailableOutfits(): Outfit[] {
    return outfits.value.filter((o) => o && !o.dweller_id)
  }

  return {
    // State
    weapons,
    outfits,
    isLoading,
    error,
    // Actions
    fetchWeapons,
    fetchOutfits,
    equipWeapon,
    unequipWeapon,
    equipOutfit,
    unequipOutfit,
    // Getters
    getEquippedWeapon,
    getEquippedOutfit,
    getAvailableWeapons,
    getAvailableOutfits,
  }
})
