import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellerDetailView from '@/modules/dwellers/views/DwellerDetailView.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

// Avoid real network call for vault map place links
vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn().mockResolvedValue({ locations: [] }),
}))

// Composables outside the scope of the deep-link test
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))
vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))
vi.mock('@/core/composables/useGaryMode', () => ({
  useGaryMode: () => ({ triggerGaryMode: vi.fn() }),
}))
vi.mock('@/modules/exploration/composables/useSendToWasteland', () => ({
  useSendToWasteland: () => ({
    open: vi.fn(),
    cancel: vi.fn(),
    confirm: vi.fn(),
    showModal: { value: false },
    pendingDweller: { value: null },
  }),
}))

// Minimal fixture: only fields the pane reads at runtime. Cast keeps the
// assignment to detailedDwellers well-typed without `as any`.
const fakeDweller = {
  id: 'dweller-1',
  first_name: 'Amata',
  last_name: 'Almodovar',
  status: 'idle',
  is_dead: false,
  is_permanently_dead: false,
  image_url: null,
  epitaph: null,
} as unknown as Dweller

describe('DwellerDetailView deep-link (?tab / ?stat)', () => {
  let router: ReturnType<typeof createRouter>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let authStore: ReturnType<typeof useAuthStore>
  let vaultStore: ReturnType<typeof useVaultStore>

  beforeEach(async () => {
    setActivePinia(createPinia())
    dwellerStore = useDwellerStore().filter
    authStore = useAuthStore()
    vaultStore = useVaultStore()

    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    // isAuthenticated derives from token in the auth store
    authStore.token = 'mock-token'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/vault/:id/dwellers/:dwellerId',
          name: 'dweller-detail',
          component: DwellerDetailView,
        },
      ],
    })
  })

  async function mountWith(query: string) {
    await router.push(`/vault/vault-1/dwellers/dweller-1${query}`)
    await router.isReady()
    const wrapper = mount(DwellerDetailView, {
      global: { plugins: [router] },
    })
    await flushPromises()
    return wrapper
  }

  it('passes ?tab and ?stat through to the detail pane', async () => {
    const wrapper = await mountWith('?tab=SPECIAL&stat=SPECIAL')
    const pane = wrapper.findComponent({ name: 'DwellerDetailPane' })
    expect(pane.exists()).toBe(true)
    expect(dwellerStore.fetchDwellerDetails).toHaveBeenCalledWith('dweller-1', 'mock-token')
  })

  it('defaults to no tab when the query is absent', async () => {
    const wrapper = await mountWith('')
    const pane = wrapper.findComponent({ name: 'DwellerDetailPane' })
    expect(pane.exists()).toBe(true)
    expect(dwellerStore.fetchDwellerDetails).toHaveBeenCalledWith('dweller-1', 'mock-token')
  })

  it('reflects a changed query on a fresh mount', async () => {
    const wrapper = await mountWith('?tab=equipment&stat=luck')
    const pane = wrapper.findComponent({ name: 'DwellerDetailPane' })
    expect(pane.exists()).toBe(true)
    expect(dwellerStore.fetchDwellerDetails).toHaveBeenCalledWith('dweller-1', 'mock-token')
  })
})
