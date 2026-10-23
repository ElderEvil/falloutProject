import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import IntroHandoffCard from '@/modules/progression/components/IntroHandoffCard.vue'
import axios from '@/core/plugins/axios'
import { useVaultStore, type VaultWithNumbers } from '@/modules/vault/stores/vault'

vi.mock('@/core/plugins/axios')
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 'token' }) }))
const router = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => router }))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ error: vi.fn(), success: vi.fn() }),
}))

const run = (vaultId = 'v1', status = 'active') => ({
  id: `run-${vaultId}`,
  vault_id: vaultId,
  dweller_id: 'explorer',
  status,
  duration: 1,
  start_time: new Date().toISOString(),
})
const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'crew',
  first_name: 'Sarah',
  last_name: 'Lyons',
  age_group: 'adult',
  health: 50,
  status: 'idle',
  room_id: null,
  ...overrides,
})
let roster: ReturnType<typeof dweller>[]
let runs: ReturnType<typeof run>[]
let equipment: unknown[]
let inventoryFailure: boolean
const wrappers: ReturnType<typeof mount>[] = []
const mountCard = () => {
  const wrapper = mount(IntroHandoffCard, { props: { vaultId: 'v1' } })
  wrappers.push(wrapper)
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  setActivePinia(createPinia())
  roster = []
  runs = [run(), run('v2')]
  equipment = []
  inventoryFailure = false
  vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.mocked(axios.get).mockImplementation(async (url) => {
    if (url.startsWith('/api/v1/dwellers/')) return { data: roster }
    if (url.startsWith('/api/v1/explorations/')) return { data: runs }
    if (url.startsWith('/api/v1/storage/')) {
      if (inventoryFailure) throw new Error('Storage unavailable')
      return { data: { weapons: equipment, outfits: [], junk: [], items: [], pets: [] } }
    }
    throw new Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
})

describe('IntroHandoffCard', () => {
  it('shows loading honestly, then the current vault run and an optional calm handoff', async () => {
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('Checking your vault')
    expect(wrapper.text()).not.toContain('Nothing else is required')
    await flushPromises()
    expect(wrapper.text()).toContain('While they’re away')
    expect(wrapper.text()).toContain('Nothing else is required by this guide')
    const view = wrapper.findAll('button').find((button) => button.text() === 'View expedition')!
    await view.trigger('click')
    expect(router.push).toHaveBeenCalledWith('/vault/v1/exploration/run-v1')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Finish intro')!
      .trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })

  it('prioritizes a real resource warning over assignment and equipment', async () => {
    useVaultStore().loadedVaults.v1 = {
      resource_warnings: [{ type: 'power', message: 'Power is draining.' }],
    } as VaultWithNumbers
    roster = [dweller()]
    equipment = [{ id: 'weapon' }]
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.text()).toContain('Power is draining')
    expect(wrapper.text()).not.toContain('Sarah')
    expect(wrapper.text()).not.toContain('Review equipment')
  })

  it('suggests only a living, available adult and excludes away, dead and young dwellers', async () => {
    roster = [
      dweller({ first_name: 'Away', status: 'exploring' }),
      dweller({ first_name: 'Child', age_group: 'child' }),
      dweller({ first_name: 'Wounded', health: 0 }),
      dweller(),
    ]
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.text()).toContain('Sarah Lyons is available for a job')
    expect(wrapper.text()).not.toContain('Review equipment')
  })

  it('suggests equipment only when stock is present, otherwise offers the Briefing', async () => {
    equipment = [{ id: 'weapon' }]
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.text()).toContain('Review equipment')
    equipment = []
    await (wrapper.vm as unknown as { refresh: () => Promise<void> }).refresh()
    expect(wrapper.text()).toContain('Check the Briefing')
  })

  it('does not invent an away explorer from another vault, and handles a return', async () => {
    runs = [run('v2')]
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.text()).toContain('No explorers are currently away')
    expect(wrapper.text()).not.toContain('View expedition')
    runs = [run('v1', 'returning')]
    await (wrapper.vm as unknown as { refresh: () => Promise<void> }).refresh()
    expect(wrapper.text()).toContain('Your explorer is heading home')
  })

  it('offers retry on failed reads instead of treating unknown data as an empty vault', async () => {
    inventoryFailure = true
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.text()).toContain('Could not refresh your vault')
    expect(wrapper.text()).not.toContain('Nothing else is required')
    inventoryFailure = false
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Retry')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Check the Briefing')
  })

  it('ignores late inventory results from a previous vault', async () => {
    let resolveOld!: (value: unknown) => void
    const original = vi.mocked(axios.get).getMockImplementation()!
    vi.mocked(axios.get).mockImplementation((url, options) =>
      url === '/api/v1/storage/vault/v1/items'
        ? new Promise((resolve) => {
            resolveOld = resolve
          })
        : original(url, options)
    )
    const wrapper = mountCard()
    await flushPromises()
    await wrapper.setProps({ vaultId: 'v2' })
    await flushPromises()
    resolveOld({ data: { weapons: [{ id: 'old-weapon' }], outfits: [] } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('Review equipment')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'View expedition')!
      .trigger('click')
    expect(router.push).toHaveBeenCalledWith('/vault/v2/exploration/run-v2')
  })
})
