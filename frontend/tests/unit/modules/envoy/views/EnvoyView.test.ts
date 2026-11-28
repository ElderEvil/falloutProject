import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock, createRouterMock, createToastMock } from '../../../helpers/mocks'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { EnvoyConfig, EnvoyFiling, EnvoySignal } from '@/modules/envoy/models/envoy'
import EnvoyView from '@/modules/envoy/views/EnvoyView.vue'

const api = vi.hoisted(() => ({
  signals: vi.fn(),
  hail: vi.fn(),
  respond: vi.fn(),
  log: vi.fn(),
  config: vi.fn(),
}))
const flags = vi.hoisted(() => ({
  loaded: true,
  vaultDiplomacy: true,
  fetchFlags: vi.fn(),
}))

vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => createToastMock() }))
vi.mock('@/core/stores/featureFlags', () => ({ useFeatureFlagsStore: () => flags }))
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

function mountView() {
  return mount(EnvoyView, {
    global: {
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
}

describe('EnvoyView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    flags.loaded = true
    flags.vaultDiplomacy = true
    api.signals.mockResolvedValue([reachable])
    api.log.mockResolvedValue([pendingHail])
    api.config.mockResolvedValue(CONFIG)
  })

  it('renders the terminal header, its four tabs and the inbox count', async () => {
    const wrapper = mountView()
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
  })

  it('renders TERMINAL OFFLINE with the reason when diplomacy is off', async () => {
    flags.vaultDiplomacy = false
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('TERMINAL OFFLINE')
    expect(wrapper.text()).toContain('Vault diplomacy is disabled on this server')
    expect(wrapper.findAll('button').some((button) => button.text() === 'SIGNALS')).toBe(false)
    expect(api.signals).not.toHaveBeenCalled()
  })
})
