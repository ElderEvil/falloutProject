import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import WastelandPanel from '@/modules/exploration/components/WastelandPanel.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

// Mock useToast
const mockToast = {
  success: vi.fn(),
  info: vi.fn(),
  error: vi.fn(),
}
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

// Mock usePolling to be a no-op (don't fire callbacks during tests)
vi.mock('@/core/composables/usePolling', () => ({
  usePolling: vi.fn(() => ({
    run: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    isActive: { value: false },
    isRefreshing: { value: false },
  })),
}))

describe('WastelandPanel', () => {
  let router: ReturnType<typeof createRouter>
  let explorationStore: ReturnType<typeof useExplorationStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']

  beforeEach(async () => {
    setActivePinia(createPinia())

    explorationStore = useExplorationStore()
    const dwellerStoreSlices = useDwellerStore()
    dwellerStore = dwellerStoreSlices.filter
    const vaultStore = useVaultStore()
    const authStore = useAuthStore()

    // Set up auth
    authStore.token = 'mock-token'
    authStore.user = { is_superuser: false } as never

    // Set up vault data for medical supplies
    vaultStore.loadedVaults['test-vault-id'] = {
      id: 'test-vault-id',
      stimpack: 10,
      radaway: 10,
    } as never

    // Mock store methods
    vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([])
    vi.spyOn(explorationStore, 'sendDwellerToWasteland').mockResolvedValue({} as never)
    vi.spyOn(explorationStore, 'recallDweller').mockResolvedValue({})
    vi.spyOn(explorationStore, 'completeExploration').mockResolvedValue({})
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(null)
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue(undefined)
    vi.spyOn(vaultStore, 'loadVault').mockResolvedValue(undefined)
    vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue(undefined)

    // Clear state
    explorationStore.activeExplorations = {}
    dwellerStore.dwellers = []
    dwellerStore.detailedDwellers = {}

    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })

    router.push('/vault/test-vault-id')
    await router.isReady()
  })

  describe('rendering', () => {
    it('renders "The Wasteland" dropzone title', async () => {
      const wrapper = mount(WastelandPanel, {
        global: {
          plugins: [router],
          stubs: {
            ActiveExplorationList: { template: '<div class="exploration-list-mock"></div>' },
            ExplorationRewardsModal: { template: '<div class="rewards-mock"></div>' },
          },
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('The Wasteland')
      expect(wrapper.text()).toContain('Drag dwellers here to send them exploring')
    })

    it('shows the empty-explorer state when no explorations', async () => {
      const wrapper = mount(WastelandPanel, {
        global: {
          plugins: [router],
          stubs: {
            ActiveExplorationList: false, // don't stub — let it render
            ExplorationRewardsModal: { template: '<div class="rewards-mock"></div>' },
          },
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('No active explorers')
    })
  })

  describe('drop flow', () => {
    it('opens the duration modal on drop-dweller', async () => {
      const wrapper = mount(WastelandPanel, {
        global: {
          plugins: [router],
          stubs: {
            ActiveExplorationList: { template: '<div class="exploration-list-mock"></div>' },
            ExplorationRewardsModal: { template: '<div class="rewards-mock"></div>' },
          },
        },
      })

      await flushPromises()

      // Simulate drop via the WastelandDropzone component's emit
      const dropzone = wrapper.findComponent({ name: 'WastelandDropzone' })
      await dropzone.vm.$emit('drop-dweller', {
        dwellerId: 'dweller-1',
        firstName: 'Test',
        lastName: 'Dweller',
        currentRoomId: undefined,
      })

      await flushPromises()

      // Duration modal should now be visible
      const durationModal = wrapper.findComponent({ name: 'ExplorationDurationModal' })
      expect(durationModal.props('show')).toBe(true)
      expect(durationModal.props('dwellerName')).toBe('Test')
    })

    it('refreshes vault supplies after sending a dweller', async () => {
      const wrapper = mount(WastelandPanel, {
        global: {
          plugins: [router],
          stubs: {
            ActiveExplorationList: { template: '<div />' },
            ExplorationRewardsModal: { template: '<div />' },
          },
        },
      })
      const dropzone = wrapper.findComponent({ name: 'WastelandDropzone' })
      await dropzone.vm.$emit('drop-dweller', { dwellerId: 'dweller-1', firstName: 'Test', lastName: 'Dweller' })
      await wrapper.findComponent({ name: 'ExplorationDurationModal' }).vm.$emit('confirm', {
        duration: 4,
        stimpaks: 1,
        radaways: 1,
      })
      await flushPromises()

      expect(useVaultStore().refreshVault).toHaveBeenCalledWith('test-vault-id', 'mock-token')
    })
  })

  describe('error handling', () => {
    it('shows toast error on drop-error', async () => {
      const wrapper = mount(WastelandPanel, {
        global: {
          plugins: [router],
          stubs: {
            ActiveExplorationList: { template: '<div class="exploration-list-mock"></div>' },
            ExplorationRewardsModal: { template: '<div class="rewards-mock"></div>' },
          },
        },
      })

      await flushPromises()

      const dropzone = wrapper.findComponent({ name: 'WastelandDropzone' })
      await dropzone.vm.$emit('drop-error', 'Failed to send dweller to wasteland')

      expect(mockToast.error).toHaveBeenCalledWith('Failed to send dweller to wasteland')
    })
  })
})
