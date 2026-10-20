import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { afterEach } from 'vitest'
import * as trainingService from '@/modules/progression/services/trainingService'

enableAutoUnmount(afterEach)
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
  setContinuousTraining: vi.fn(async (_vaultId: string, enabled: boolean) => ({
    continuous_training: enabled,
  })),
}))

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
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
            Tooltip: { template: '<div><slot /></div>' },
            TooltipTrigger: { template: '<div><slot /></div>' },
            TooltipContent: { template: '<div><slot /></div>' },
          },
        },
      })

      // After mount, vault is null → fetchTrainings should bail early
      expect(fetchSpy).not.toHaveBeenCalled()

      // Clear the initial call count
      fetchSpy.mockClear()

      // Simulate vault loading after mount (as TrainingView's ensureVaultLoaded would do)
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

  it('replaces refresh with a persistent continuous-training toggle', async () => {
    vaultStore.loadedVaults['vault-1'] = {
      id: 'vault-1',
      number: 1,
      continuous_training: false,
    } as any
    vaultStore.activeVaultId = 'vault-1'
    wrapper = mount(TrainingQueuePanel, {
      global: {
        stubs: {
          Icon: true,
          Tooltip: { template: '<div><slot /></div>' },
          TooltipTrigger: { template: '<div><slot /></div>' },
          TooltipContent: { template: '<div><slot /></div>' },
        },
      },
    })
    await flushPromises()
    const toggle = wrapper.get('button[aria-label="Continuous training"]')
    expect(toggle.attributes('aria-pressed')).toBe('false')
    await toggle.trigger('click')
    await flushPromises()
    expect(trainingService.setContinuousTraining).toHaveBeenCalledWith(
      'vault-1',
      true,
      'mock-token'
    )
    expect(toggle.attributes('aria-pressed')).toBe('true')
    await toggle.trigger('click')
    await flushPromises()
    expect(trainingService.setContinuousTraining).toHaveBeenLastCalledWith(
      'vault-1',
      false,
      'mock-token'
    )
    expect(toggle.attributes('aria-pressed')).toBe('false')
  })
})
