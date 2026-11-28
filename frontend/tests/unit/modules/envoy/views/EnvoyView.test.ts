import { beforeEach, describe, expect, it, vi, type Mock } from 'vite-plus/test'
import { createIconifyMock, createToastMock } from '../../../helpers/mocks'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import TerminalConfirmation from '@/core/components/common/TerminalConfirmation.vue'
import HailDialog from '@/modules/envoy/components/HailDialog.vue'
import SignalList from '@/modules/envoy/components/SignalList.vue'
import EnvoyView from '@/modules/envoy/views/EnvoyView.vue'
import type { EnvoyConfig, EnvoyFiling, EnvoySignal } from '@/modules/envoy/models/envoy'

const api = vi.hoisted(() => ({
  signals: vi.fn(),
  hail: vi.fn(),
  respond: vi.fn(),
  log: vi.fn(),
  config: vi.fn(),
}))
interface FlagsMock {
  loaded: boolean
  vaultDiplomacy: boolean
  fetchFlags: Mock
}
const flagsState = vi.hoisted(() => ({ store: null as unknown as FlagsMock }))

vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('@/core/composables/useToast', () => ({ useToast: () => createToastMock() }))
// Reactive: the terminal branches on `loaded`, so a plain object would freeze the render.
vi.mock('@/core/stores/featureFlags', async () => {
  const { reactive } = await import('vue')
  const store = reactive({ loaded: true, vaultDiplomacy: true, fetchFlags: vi.fn() })
  flagsState.store = store
  return { useFeatureFlagsStore: () => store }
})
vi.mock('@/modules/envoy/services/envoyService', () => ({ envoyService: api }))

const CONFIG: EnvoyConfig = {
  enabled: true,
  trade_gate: 'standoff',
  hail_radius: 2,
  filing_ttl_hours: 48,
  refusal_lock_hours: 24,
  repropose_hours: 72,
  ceasefire_days: 7,
  war_upkeep_per_level: 10,
  footing_penalty_pct: 5,
  fatigue_start_days: 14,
  fatigue_ramp_days: 7,
  arbitration_day: 3,
  accord_upkeep: 300,
  compact_upkeep: 1500,
  unjust_war_multiplier: 2,
  stake_pct: 10,
  stake_min: 50,
  stake_max: 500,
}

const reachable: EnvoySignal = {
  vault_id: 'vault-2',
  number: 7,
  owner_username: 'ada',
  status: 'UNMET',
  standing: 0,
  distance: 1.2,
  can_hail: true,
  incoming_hail: false,
}

const pendingHail: EnvoyFiling = {
  filing_id: 'filing-1',
  kind: 'HAIL',
  status: 'PENDING',
  from_vault_id: 'vault-2',
  to_vault_id: 'vault-1',
  terms: {},
  incoming: true,
  created_at: '2026-01-01T00:00:00Z',
  expires_at: '2026-01-03T00:00:00Z',
  responded_at: null,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => {
    resolve = settle
  })
  return { promise, resolve }
}

/** A real router: the vault switch has to move `route.params.id`, a plain mock cannot. */
async function mountView(vault = 'vault-1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
  })
  await router.push(`/vault/${vault}`)
  await router.isReady()
  const wrapper = mount(EnvoyView, {
    global: {
      plugins: [router],
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        VaultPageShell: { template: '<main><slot /></main>' },
        PageHeader: {
          props: ['title', 'subtitle'],
          template:
            '<header><h1>{{ title }}</h1><p>{{ subtitle }}</p><slot name="actions" /></header>',
        },
        TradingPostPanel: true,
      },
    },
  })
  return { wrapper, router }
}

describe('EnvoyView', () => {
  let flags: FlagsMock

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    flags = flagsState.store
    flags.loaded = true
    flags.vaultDiplomacy = true
    flags.fetchFlags.mockReset()
    api.signals.mockResolvedValue([reachable])
    api.log.mockResolvedValue([pendingHail])
    api.config.mockResolvedValue(CONFIG)
  })

  it('renders the terminal header, its four tabs and the inbox count', async () => {
    const { wrapper } = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('ENVOY TERMINAL')
    expect(wrapper.text()).toContain('Inter-vault relations · emergency band 47.2')
    const tabs = wrapper.findAll('button').map((button) => button.text())
    for (const label of ['SIGNALS', 'INBOX', 'LABOUR', 'LOG']) {
      expect(tabs.some((text) => text.startsWith(label))).toBe(true)
    }
    expect(wrapper.text()).toContain('VAULT 7')
    expect(wrapper.findAll('[data-slot="badge"]').map((badge) => badge.text())).toContain('1')
    expect(api.config).toHaveBeenCalledWith('vault-1')
    expect(flags.fetchFlags).not.toHaveBeenCalled()
  })

  it('renders TERMINAL OFFLINE with the reason when diplomacy is off', async () => {
    flags.vaultDiplomacy = false
    const { wrapper } = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('TERMINAL OFFLINE')
    expect(wrapper.text()).toContain('Vault diplomacy is disabled on this server')
    expect(wrapper.findAll('button').some((button) => button.text() === 'SIGNALS')).toBe(false)
    expect(api.signals).not.toHaveBeenCalled()
  })

  it('retries a failed flag fetch on the next sweep instead of tuning forever', async () => {
    flags.loaded = false
    flags.vaultDiplomacy = false
    const { wrapper } = await mountView()
    await flushPromises()

    expect(flags.fetchFlags).toHaveBeenCalledTimes(1)
    expect(api.signals).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Tuning the emergency band')

    flags.fetchFlags.mockImplementation(async () => {
      flags.loaded = true
      flags.vaultDiplomacy = true
    })
    const retry = wrapper.findAll('button').find((button) => button.text().includes('Refresh'))
    await retry!.trigger('click')
    await flushPromises()

    expect(flags.fetchFlags).toHaveBeenCalledTimes(2)
    expect(api.signals).toHaveBeenCalledWith('vault-1')
    expect(wrapper.text()).toContain('VAULT 7')
  })

  it('keeps the response dialog open with the store reason when the answer fails', async () => {
    api.respond.mockRejectedValue(
      Object.assign(new Error('Conflict'), {
        name: 'ApiError',
        detail: 'That hail already expired.',
        status: 409,
      })
    )
    const { wrapper } = await mountView()
    await flushPromises()

    // The roster answers by vault; the store resolves which pending hail that is.
    wrapper.findComponent(SignalList).vm.$emit('respond', reachable, true)
    await flushPromises()
    const dialog = wrapper.findComponent(TerminalConfirmation)
    expect(dialog.props('open')).toBe(true)

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(dialog.props('open')).toBe(true)
    expect(wrapper.text()).toContain('That hail already expired.')
  })

  it('clears both pending dialogs when the vault changes', async () => {
    const { wrapper, router } = await mountView()
    await flushPromises()

    wrapper.findComponent(SignalList).vm.$emit('hail', reachable)
    wrapper.findComponent(SignalList).vm.$emit('respond', reachable, true)
    await flushPromises()
    expect(wrapper.findComponent(HailDialog).props('signal')).toEqual(reachable)
    expect(wrapper.findComponent(TerminalConfirmation).props('open')).toBe(true)

    await router.push('/vault/vault-2')
    await flushPromises()

    expect(wrapper.findComponent(HailDialog).props('signal')).toBeNull()
    expect(wrapper.findComponent(TerminalConfirmation).props('open')).toBe(false)
    expect(api.signals).toHaveBeenCalledWith('vault-2')
  })

  it('does not start the terminal when the view unmounts while the flags load', async () => {
    flags.loaded = false
    const flagFetch = deferred<void>()
    flags.fetchFlags.mockReturnValueOnce(flagFetch.promise)
    const { wrapper } = await mountView()

    wrapper.unmount()
    flagFetch.resolve()
    await flushPromises()

    // A sweep that outlives the view must not re-arm the poller behind it.
    expect(api.signals).not.toHaveBeenCalled()
  })
})
