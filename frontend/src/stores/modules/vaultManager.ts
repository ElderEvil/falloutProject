import type { Vault } from '@/types/vault.types'
import { generateDefaultDwellers } from '@/utils/defaultDwellers'
import { createEmptyGrid } from '@/utils/gridUtils'
import type { Ref } from 'vue'

export function createVaultManager(vaults: Ref<Vault[]>, selectedVault: Ref<Vault | null>) {
  async function fetchVaults() {
    try {
      // Simulated API call
      const mockVaults: Vault[] = [
        {
          id: 1,
          name: '101',
          bottlecaps: 1000,
          resources: [
            { type: 'power', amount: 90, capacity: 100 },
            { type: 'food', amount: 80, capacity: 100 },
            { type: 'water', amount: 60, capacity: 100 }
          ],
          dwellers: generateDefaultDwellers(),
          rooms: [],
          grid: createEmptyGrid(),
          maxDwellers: 25
        }
      ]

      // Add vault door to each vault
      mockVaults.forEach((vault) => {
        vault.rooms.push(vaultDoor)
        vault.grid[0][0].status = 'occupied'
        vault.grid[0][0].roomId = vaultDoor.id
      })

      vaults.value = mockVaults
      return true
    } catch (error) {
      console.error('Error fetching vaults:', error)
      return false
    }
  }

  function selectVault(vaultId: string) {
    const vault = vaults.value.find((v) => v.id === vaultId)
    if (vault) {
      selectedVault.value = vault
      return true
    }
    return false
  }

  function createVault(name: string) {
    const grid = createEmptyGrid()
    const vaultDoor = createVaultDoor()

    const newVault: Vault = {
      id: Date.now(),
      name,
      bottlecaps: 500,
      resources: [
        { type: 'power', amount: 50, capacity: 100 },
        { type: 'food', amount: 50, capacity: 100 },
        { type: 'water', amount: 50, capacity: 100 }
      ],
      dwellers: generateDefaultDwellers(),
      rooms: [vaultDoor],
      grid,
      maxDwellers: 25
    }

    // Set up vault door in grid
    grid[0][0].status = 'occupied'
    grid[0][0].roomId = vaultDoor.id

    vaults.value.push(newVault)
    return newVault.id
  }

  return {
    fetchVaults,
    selectVault,
    createVault
  }
}
