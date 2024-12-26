import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Vault } from '@/types/vault.types'
import { createVaultManager } from './modules/vaultManager'
import { createDwellerManager } from './modules/dwellerManager'
import { createRoomManager } from './modules/roomManager'
import { createResourceManager } from './modules/resourceManager'

export const useVaultStore = defineStore('vault', () => {
  const vaults = ref<Vault[]>([])
  const selectedVault = ref<Vault | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const getSelectedVault = () => selectedVault.value

  const vaultManager = createVaultManager(vaults, selectedVault)
  const dwellerManager = createDwellerManager(getSelectedVault)
  const roomManager = createRoomManager(getSelectedVault, dwellerManager.unassignDweller)
  const resourceManager = createResourceManager(getSelectedVault)

  // Grid management functions
  function startDigging(position: { x: number; y: number }) {
    return roomManager.startDigging(position.x, position.y)
  }

  function completeDigging(position: { x: number; y: number }) {
    return roomManager.completeDigging(position.x, position.y)
  }

  function startConstruction(position: { x: number; y: number }) {
    return roomManager.startConstruction(position.x, position.y)
  }

  function getRoomById(roomId: string) {
    return roomManager.getRoomById(roomId)
  }

  return {
    // State
    vaults,
    selectedVault,
    loading,
    error,

    // Vault management
    ...vaultManager,

    // Dweller management
    ...dwellerManager,

    // Room management
    ...roomManager,

    // Resource management
    ...resourceManager,

    // Grid management
    startDigging,
    completeDigging,
    startConstruction,
    getRoomById
  }
})
