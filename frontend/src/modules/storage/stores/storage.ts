import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { handleStoreError } from '@/core/utils/errorHandler'
import {
  storageService,
  type StorageItemsResponse,
  type StorageMaintenance,
} from '../services/storageService'
import type { components } from '@/core/types/api.generated'

export const useStorageStore = defineStore('storage', () => {
  const vaultId = ref<string | null>(null)
  const items = ref<StorageItemsResponse>({
    weapons: [],
    outfits: [],
    junk: [],
    items: [],
    pets: [],
  })
  const space = ref<components['schemas']['StorageSpaceResponse'] | null>(null)
  const maintenance = ref<StorageMaintenance | null>(null)
  const isLoading = ref(false)
  const maintenanceMode = computed(() => {
    const mode = maintenance.value?.mode ?? 'disabled'
    return mode.charAt(0).toUpperCase() + mode.slice(1)
  })
  const maintenanceLabel = computed(() => {
    const value = maintenance.value
    if (!value?.enabled) return 'Maintenance inactive'
    const interval =
      value.trial_interval_seconds === 3600 ? 'hour' : `${value.trial_interval_seconds / 60} min`
    return `${maintenanceMode.value} · ${(value.hourly_chance * 100).toFixed(1)}% / ${interval}`
  })
  let sequence = 0
  const consumers = new Set<symbol>()

  async function refresh(id: string): Promise<'loaded' | 'stale' | 'error'> {
    const request = ++sequence
    if (vaultId.value !== id) {
      items.value = { weapons: [], outfits: [], junk: [], items: [], pets: [] }
      space.value = null
      maintenance.value = null
    }
    vaultId.value = id
    isLoading.value = true
    try {
      const [nextSpace, nextItems, nextMaintenance] = await Promise.all([
        storageService.getStorageSpace(id),
        storageService.getStorageItems(id),
        storageService.getMaintenance(id),
      ])
      if (request !== sequence) return 'stale'
      space.value = nextSpace
      items.value = nextItems
      maintenance.value = nextMaintenance
      return 'loaded'
    } catch (error) {
      if (request === sequence) {
        console.error('Failed to refresh vault storage', error)
        handleStoreError(error, 'Failed to refresh storage', false)
        return 'error'
      }
      return 'stale'
    } finally {
      if (request === sequence) isLoading.value = false
    }
  }

  function refreshIfActive(id: string) {
    if (consumers.size && vaultId.value === id) void refresh(id)
  }

  function retain() {
    const consumer = Symbol()
    consumers.add(consumer)
    return () => {
      if (consumers.delete(consumer) && consumers.size === 0) reset()
    }
  }

  function reset() {
    sequence++
    vaultId.value = null
    items.value = { weapons: [], outfits: [], junk: [], items: [], pets: [] }
    space.value = null
    maintenance.value = null
    isLoading.value = false
  }

  return {
    ...storageService,
    reset,
    retain,
    vaultId,
    items,
    space,
    maintenance,
    isLoading,
    maintenanceLabel,
    maintenanceMode,
    refresh,
    refreshIfActive,
  }
})
