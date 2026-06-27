import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TrainingQueuePanel from '@/modules/progression/components/training/TrainingQueuePanel.vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'

// Mock training service to prevent real HTTP calls
vi.mock('@/modules/progression/services/trainingService', () => ({
  getVaultTrainings: vi.fn().mockResolvedValue([]),
  getDwellerTraining: vi.fn().mockResolvedValue(null),
  getRoomTrainings: vi.fn().mockResolvedValue([]),
  getTrainingProgress: vi.fn().mockResolvedValue(null),
  startTraining: vi.fn().mockResolvedValue({ id: 't-1' }),
  cancelTraining: vi.fn().mockResolvedValue({ id: 't-1', status: 'cancelled' }),
  completeTraining: vi.fn().mockResolvedValue({ id: 't-1', status: 'completed' }),
}))

describe('TrainingQueuePanel', () => {
  let wrapper: VueWrapper
  let trainingStore: ReturnType<typeof useTrainingStore>
  let authStore: ReturnType<typeof useAuthStore>
  let vaultStore: ReturnType<typeof useVaultStore>

  beforeEach(() => {
    setActivePinia(createPinia())

    trainingStore = useTrainingStore()
    authStore = useAuthStore()
    vaultStore = useVaultStore()

    vi.clearAllMocks()

    // Set auth token so fetchTrainings doesn't bail on auth check
    authStore.token = 'mock-token'
  })

  describe('page reload (vault loads after mount)', () => {
    it('should fetch trainings when vault becomes available after mount', async () => {
      // Spy on fetchVaultTrainings to track calls
      const fetchSpy = vi.spyOn(trainingStore, 'fetchVaultTrainings').mockResolvedValue()

      // Mount with NO active vault — simulates page reload where vault hasn't loaded yet
      wrapper = mount(TrainingQueuePanel, {
        global: {
          stubs: {
            Icon: true,
            TrainingProgressCard: true,
          },
        },
      })

      // After mount, vault is null → fetchTrainings should bail early
      expect(fetchSpy).not.toHaveBeenCalled()

      // Clear the initial call count
      fetchSpy.mockClear()

      // Simulate vault loading after mount (as TrainingView.loadVault would do)
      vaultStore.loadedVaults = {
        'vault-1': { id: 'vault-1', number: 1, name: 'Vault 1' } as any,
      }
      vaultStore.activeVaultId = 'vault-1'

      // Wait for any watchers/effects to fire
      await new Promise((r) => setTimeout(r, 50))

      // BUG: fetchVaultTrainings should have been called now that vault is available,
      // but it wasn't — there's no watcher to react to activeVault changing
      expect(fetchSpy).toHaveBeenCalledWith('vault-1', 'mock-token')
    })
  })
})
