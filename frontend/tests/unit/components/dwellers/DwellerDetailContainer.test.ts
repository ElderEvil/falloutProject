import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellerDetailContainer from '@/modules/dwellers/components/DwellerDetailContainer.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
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

// Composables outside the scope of this test
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

describe('DwellerDetailContainer', () => {
  let router: ReturnType<typeof createRouter>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(async () => {
    setActivePinia(createPinia())
    dwellerStore = useDwellerStore().filter
    authStore = useAuthStore()

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
          name: 'dwellerDetail',
          component: DwellerDetailContainer,
        },
        {
          path: '/vault/:id/dwellers',
          name: 'dwellers',
          component: { template: '<div>Dwellers list</div>' },
        },
      ],
    })
  })

  async function mountAt(path: string) {
    await router.push(path)
    await router.isReady()
    const wrapper = mount(DwellerDetailContainer, {
      global: { plugins: [router] },
    })
    await flushPromises()
    return wrapper
  }

  it('reads the dweller from the :dwellerId route param', async () => {
    const wrapper = await mountAt('/vault/vault-1/dwellers/dweller-1?tab=SPECIAL&stat=SPECIAL')
    const pane = wrapper.findComponent({ name: 'DwellerDetailPane' })
    expect(pane.exists()).toBe(true)
    expect(pane.props('initialTab')).toBe('SPECIAL')
    expect(pane.props('highlightStat')).toBe('special')
  })

  it('shows not-found when no :dwellerId param is present', async () => {
    const wrapper = await mountAt('/vault/vault-1/dwellers')
    expect(wrapper.findComponent({ name: 'DwellerDetailPane' }).exists()).toBe(false)
    expect(wrapper.text()).toContain('Dweller not found')
  })

  it('navigates back to the dwellers list on back', async () => {
    const wrapper = await mountAt('/vault/vault-1/dwellers/dweller-1')
    const back = wrapper.findComponent({ name: 'BackButton' })
    expect(back.exists()).toBe(true)
    await back.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('dwellers')
  })
})
