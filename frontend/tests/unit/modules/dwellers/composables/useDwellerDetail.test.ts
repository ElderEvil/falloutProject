import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createToastMock } from '../../../helpers/mocks'
import { defineComponent, nextTick, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useDwellerDetail } from '@/modules/dwellers/composables/useDwellerDetail'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// Avoid real network call for vault map place links
vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn().mockResolvedValue({ locations: [] }),
}))

const mockToast = createToastMock()

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))
vi.mock('@/core/composables/useGaryMode', () => ({
  useGaryMode: () => ({ triggerGaryMode: vi.fn() }),
}))
vi.mock('@/modules/exploration/composables/useSendToWasteland', () => ({
  useSendToWasteland: () => ({
    open: vi.fn(),
    cancel: vi.fn(),
    confirm: vi.fn(),
    reroll: vi.fn(),
    showModal: { value: false },
    pendingDweller: { value: null },
    headingDegrees: { value: null },
    isSuggestingHeading: { value: false },
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

    const detail = (
      wrapper.vm as unknown as { detail: { actions: { confirmSoftDelete: () => Promise<void> } } }
    ).detail
    await detail.actions.confirmSoftDelete()
    await flushPromises()

    // The record is gone: no force-refresh that would 404 and toast.
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(mockToast.error).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/vault/vault-1/dwellers')
  })
})

describe('useDwellerDetail chat deep-link', () => {
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

  it('opens chat as a query param on the same route instead of navigating to /dweller/:id/chat', async () => {
    const { filter: dwellerStore } = useDwellerStore()
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    const wrapper = mount(Harness, { global: { plugins: [router] } })
    await flushPromises()

    const detail = (
      wrapper.vm as unknown as { detail: { actions: { navigateToChat: () => void } } }
    ).detail
    detail.actions.navigateToChat()
    await flushPromises()

    // The detail route stays mounted; only the query gains ?chat=<dwellerId>.
    expect(router.currentRoute.value.path).toBe('/vault/vault-1/dwellers/dweller-1')
    expect(router.currentRoute.value.query.chat).toBe('dweller-1')
  })

  it('preserves existing query params when opening chat', async () => {
    const { filter: dwellerStore } = useDwellerStore()
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    await router.push('/vault/vault-1/dwellers/dweller-1?tab=SPECIAL&stat=luck')
    const wrapper = mount(Harness, { global: { plugins: [router] } })
    await flushPromises()

    const detail = (
      wrapper.vm as unknown as { detail: { actions: { navigateToChat: () => void } } }
    ).detail
    detail.actions.navigateToChat()
    await flushPromises()

    expect(router.currentRoute.value.query.chat).toBe('dweller-1')
    expect(router.currentRoute.value.query.tab).toBe('SPECIAL')
    expect(router.currentRoute.value.query.stat).toBe('luck')
  })
})

describe('useDwellerDetail one-click heal', () => {
  let router: ReturnType<typeof createRouter>

  const makeDweller = (overrides: Partial<Dweller> = {}) =>
    ({
      ...fakeDweller,
      health: 50,
      max_health: 100,
      radiation: 0,
      stimpack: 0,
      radaway: 0,
      visual_attributes: { race: 'human' },
      ...overrides,
    }) as unknown as Dweller

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

  async function mountDetail(dweller: Dweller, vaultStock: Record<string, number> = {}) {
    const { filter: dwellerStore, medical } = useDwellerStore()
    const vaultStore = useVaultStore()
    vaultStore.loadedVaults['vault-1'] = { stimpack: 0, radaway: 0, ...vaultStock } as never

    const fetchDetails = vi
      .spyOn(dwellerStore, 'fetchDwellerDetails')
      .mockImplementation(async (id: string) => {
        dwellerStore.detailedDwellers[id] = dweller
        return dweller
      })
    const refreshVault = vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue(undefined)
    const useStimpack = vi
      .spyOn(medical, 'useStimpack')
      .mockResolvedValue({ id: 'dweller-1' } as never)
    const useRadaway = vi.spyOn(medical, 'useRadaway').mockResolvedValue({ id: 'dweller-1' } as never)
    const issueMedicalSupply = vi
      .spyOn(medical, 'issueMedicalSupply')
      .mockResolvedValue({ stimpaks: 1 } as never)

    const wrapper = mount(Harness, { global: { plugins: [router] } })
    await flushPromises()

    const detail = (
      wrapper.vm as unknown as {
        detail: {
          healingSupply: { value: 'stimpack' | 'radaway' | null }
          actions: { healSupply: (supply: 'stimpack' | 'radaway') => Promise<void> }
        }
      }
    ).detail

    return {
      detail,
      fetchDetails,
      refreshVault,
      useStimpack,
      useRadaway,
      issueMedicalSupply,
    }
  }

  it('uses a carried supply directly without issuing from the vault', async () => {
    const { detail, useStimpack, issueMedicalSupply } = await mountDetail(
      makeDweller({ stimpack: 2 })
    )

    await detail.actions.healSupply('stimpack')
    await flushPromises()

    expect(issueMedicalSupply).not.toHaveBeenCalled()
    expect(useStimpack).toHaveBeenCalledTimes(1)
  })

  it('auto-issues from the vault, refreshes, then heals when the dweller carries none', async () => {
    const { detail, fetchDetails, refreshVault, useStimpack, issueMedicalSupply } = await mountDetail(
      makeDweller({ stimpack: 0 }),
      { stimpack: 3 }
    )
    fetchDetails.mockClear()

    await detail.actions.healSupply('stimpack')
    await flushPromises()

    expect(issueMedicalSupply).toHaveBeenCalledTimes(1)
    expect(fetchDetails).toHaveBeenCalledWith('dweller-1', 'mock-token', true)
    expect(refreshVault).toHaveBeenCalledWith('vault-1', 'mock-token')
    expect(useStimpack).toHaveBeenCalledTimes(1)
    expect(issueMedicalSupply.mock.invocationCallOrder[0]).toBeLessThan(
      useStimpack.mock.invocationCallOrder[0]
    )
  })

  it('routes RadAway through the same issue-then-use chain', async () => {
    const { detail, useRadaway, issueMedicalSupply } = await mountDetail(
      makeDweller({ radiation: 30, radaway: 0 }),
      { radaway: 2 }
    )

    await detail.actions.healSupply('radaway')
    await flushPromises()

    expect(issueMedicalSupply).toHaveBeenCalledWith('vault-1', 'dweller-1', 'radaway', 'mock-token')
    expect(useRadaway).toHaveBeenCalledTimes(1)
  })

  it('holds one busy state across both store calls', async () => {
    const { detail, issueMedicalSupply } = await mountDetail(
      makeDweller({ stimpack: 0 }),
      { stimpack: 3 }
    )
    let resolveIssue!: (value: unknown) => void
    issueMedicalSupply.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveIssue = resolve
      }) as never
    )

    const heal = detail.actions.healSupply('stimpack')
    await nextTick()

    expect(detail.healingSupply.value).toBe('stimpack')

    resolveIssue({ stimpaks: 1 })
    await heal
    await flushPromises()

    expect(detail.healingSupply.value).toBeNull()
  })

  it('stops before using when the issue leg fails', async () => {
    const { detail, useStimpack, issueMedicalSupply } = await mountDetail(
      makeDweller({ stimpack: 0 }),
      { stimpack: 3 }
    )
    issueMedicalSupply.mockResolvedValueOnce(null as never)

    await detail.actions.healSupply('stimpack')
    await flushPromises()

    expect(useStimpack).not.toHaveBeenCalled()
    expect(detail.healingSupply.value).toBeNull()
  })

  it('clears the busy state when the use leg fails', async () => {
    const { detail, useStimpack } = await mountDetail(makeDweller({ stimpack: 2 }))
    useStimpack.mockResolvedValueOnce(null as never)

    await expect(detail.actions.healSupply('stimpack')).resolves.toBeUndefined()

    expect(detail.healingSupply.value).toBeNull()
  })

  it.each([
    ['dead', makeDweller({ is_dead: true, stimpack: 2 })],
    ['uninjured', makeDweller({ health: 100, stimpack: 2 })],
    ['supply-less', makeDweller({ stimpack: 0 })],
  ])('does nothing for a %s dweller', async (_label, dweller) => {
    const { detail, useStimpack, useRadaway, issueMedicalSupply } = await mountDetail(dweller)

    await detail.actions.healSupply('stimpack')
    await flushPromises()

    expect(useStimpack).not.toHaveBeenCalled()
    expect(useRadaway).not.toHaveBeenCalled()
    expect(issueMedicalSupply).not.toHaveBeenCalled()
    expect(detail.healingSupply.value).toBeNull()
  })
})
