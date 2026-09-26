import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useDwellerDetail } from '@/modules/dwellers/composables/useDwellerDetail'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// Avoid real network call for vault map place links
vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn().mockResolvedValue({ locations: [] }),
}))

const { toastError } = vi.hoisted(() => ({ toastError: vi.fn() }))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: toastError, info: vi.fn() }),
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

const Harness = defineComponent({
  setup() {
    const detail = useDwellerDetail(ref('dweller-1'), ref('vault-1'))
    return { detail }
  },
  template: '<div />',
})

describe('useDwellerDetail soft-delete', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'mock-token'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/dwellers/:dwellerId', name: 'dweller-detail', component: Harness },
        { path: '/vault/:id/dwellers', name: 'dwellers', component: { template: '<div />' } },
      ],
    })
    await router.push('/vault/vault-1/dwellers/dweller-1')
    await router.isReady()
  })

  it('does not refetch details after soft-delete and navigates back to the roster', async () => {
    const { filter: dwellerStore, management } = useDwellerStore()
    const fetchSpy = vi
      .spyOn(dwellerStore, 'fetchDwellerDetails')
      .mockImplementation(async (id: string) => {
        dwellerStore.detailedDwellers[id] = fakeDweller
        return fakeDweller
      })
    vi.spyOn(management, 'softDeleteDweller').mockResolvedValue(fakeDweller)

    const wrapper = mount(Harness, { global: { plugins: [router] } })
    await flushPromises()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    const detail = (wrapper.vm as unknown as { detail: { actions: { confirmSoftDelete: () => Promise<void> } } }).detail
    await detail.actions.confirmSoftDelete()
    await flushPromises()

    // The record is gone: no force-refresh that would 404 and toast.
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(toastError).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/vault/vault-1/dwellers')
  })
})
