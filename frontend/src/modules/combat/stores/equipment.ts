import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Weapon, Outfit } from '../models/equipment'
import * as equipmentService from '../services/equipment'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'

export const useEquipmentStore = defineStore('equipment', () => {
  const toast = useToast()
  const authStore = useAuthStore()

  // State
  const weapons = ref<Weapon[]>([])
  const outfits = ref<Outfit[]>([])
  const error = ref<string | null>(null)
  const isWeaponsLoading = ref(false)
  const isOutfitsLoading = ref(false)
  const isLoading = computed(() => isWeaponsLoading.value || isOutfitsLoading.value)
  let weaponsRequest = 0
  let outfitsRequest = 0
  let context = ''

  function beginContext(vaultId: string): void {
    const next = `${authStore.sessionGeneration}:${vaultId}`
    if (next === context) return
    context = next
    ++weaponsRequest
    ++outfitsRequest
    weapons.value = []
    outfits.value = []
    isWeaponsLoading.value = false
    isOutfitsLoading.value = false
  }

  async function fetchWeapons(vaultId: string): Promise<void> {
    beginContext(vaultId)
    const request = ++weaponsRequest
    const session = authStore.sessionGeneration
    isWeaponsLoading.value = true
    error.value = null
    try {
      const result = await equipmentService.fetchWeapons(vaultId)
      if (request === weaponsRequest && session === authStore.sessionGeneration)
        weapons.value = result
    } catch (err) {
      if (request !== weaponsRequest || session !== authStore.sessionGeneration) return
      error.value = 'Failed to load weapons'
      handleStoreError(err, 'Failed to fetch weapons')
    } finally {
      if (request === weaponsRequest) isWeaponsLoading.value = false
    }
  }

  async function fetchOutfits(vaultId: string): Promise<void> {
    beginContext(vaultId)
    const request = ++outfitsRequest
    const session = authStore.sessionGeneration
    isOutfitsLoading.value = true
    error.value = null
    try {
      const result = await equipmentService.fetchOutfits(vaultId)
      if (request === outfitsRequest && session === authStore.sessionGeneration)
        outfits.value = result
    } catch (err) {
      if (request !== outfitsRequest || session !== authStore.sessionGeneration) return
      error.value = 'Failed to load outfits'
      handleStoreError(err, 'Failed to fetch outfits')
    } finally {
      if (request === outfitsRequest) isOutfitsLoading.value = false
    }
  }

  async function equipWeapon(dwellerId: string, weaponId: string): Promise<Weapon | null> {
    try {
      const weapon = await equipmentService.equipWeapon(dwellerId, weaponId)

      // Update local state: unequip from previous dweller, equip to new dweller
      const weaponIndex = weapons.value.findIndex((w) => w.id === weaponId)
      if (weaponIndex !== -1) {
        weapons.value[weaponIndex] = weapon
      }

      toast.success('Weapon equipped successfully!')
      return weapon
    } catch (err) {
      handleStoreError(err, 'Failed to equip weapon')
      return null
    }
  }

  async function unequipWeapon(weaponId: string): Promise<Weapon | null> {
    try {
      const weapon = await equipmentService.unequipWeapon(weaponId)

      // Update local state
      const weaponIndex = weapons.value.findIndex((w) => w.id === weaponId)
      if (weaponIndex !== -1) {
        weapons.value[weaponIndex] = weapon
      }

      toast.success('Weapon unequipped successfully!')
      return weapon
    } catch (err) {
      handleStoreError(err, 'Failed to unequip weapon')
      return null
    }
  }

  async function equipOutfit(dwellerId: string, outfitId: string): Promise<Outfit | null> {
    try {
      const outfit = await equipmentService.equipOutfit(dwellerId, outfitId)

      // Update local state: unequip from previous dweller, equip to new dweller
      const outfitIndex = outfits.value.findIndex((o) => o.id === outfitId)
      if (outfitIndex !== -1) {
        outfits.value[outfitIndex] = outfit
      }

      toast.success('Outfit equipped successfully!')
      return outfit
    } catch (err) {
      handleStoreError(err, 'Failed to equip outfit')
      return null
    }
  }

  async function unequipOutfit(outfitId: string): Promise<Outfit | null> {
    try {
      const outfit = await equipmentService.unequipOutfit(outfitId)

      // Update local state
      const outfitIndex = outfits.value.findIndex((o) => o.id === outfitId)
      if (outfitIndex !== -1) {
        outfits.value[outfitIndex] = outfit
      }

      toast.success('Outfit unequipped successfully!')
      return outfit
    } catch (err) {
      handleStoreError(err, 'Failed to unequip outfit')
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
