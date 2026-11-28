import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import type { EnvoyConfig, EnvoyFiling, EnvoySignal } from '@/modules/envoy/models/envoy'
import { useEnvoyStore } from '@/modules/envoy/stores/envoy'

const api = vi.hoisted(() => ({
  signals: vi.fn(),
  hail: vi.fn(),
  respond: vi.fn(),
  log: vi.fn(),
  config: vi.fn(),
}))

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

function signal(overrides: Partial<EnvoySignal>): EnvoySignal {
  return {
    vault_id: 'vault-2',
    number: 2,
    owner_username: 'ada',
    status: 'UNMET',
    standing: 0,
    distance: 1,
    can_hail: false,
    incoming_hail: false,
    ...overrides,
  }
}

function filing(overrides: Partial<EnvoyFiling>): EnvoyFiling {
  return {
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
    ...overrides,
  }
}

const contact = signal({ vault_id: 'vault-3', number: 3, status: 'CONTACT', distance: 0.5 })
const near = signal({ vault_id: 'vault-4', number: 4, distance: 1.5, can_hail: true })
const far = signal({ vault_id: 'vault-5', number: 5, distance: 3, can_hail: true })
const inbound = signal({
  vault_id: 'vault-6',
  number: 6,
  distance: 9,
  incoming_hail: true,
})

describe('envoy store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    api.signals.mockResolvedValue([contact, near, far, inbound])
    api.log.mockResolvedValue([])
    api.config.mockResolvedValue(CONFIG)
  })

  it('loads the band, applies the server knobs and orders the roster', async () => {
    const store = useEnvoyStore()
    await store.start('vault-1')

    expect(api.config).toHaveBeenCalledWith('vault-1')
    expect(store.config?.filing_ttl_hours).toBe(48)
    expect(store.stateVaultId).toBe('vault-1')
    expect(store.loading).toBe(false)
    expect(store.sortedSignals.map((entry) => entry.vault_id)).toEqual([
      'vault-6',
      'vault-4',
      'vault-5',
      'vault-3',
    ])
  })

  it('files a hail and marks that vault as awaiting a reply', async () => {
    const store = useEnvoyStore()
    await store.start('vault-1')
    api.hail.mockResolvedValue(
      filing({ incoming: false, from_vault_id: 'vault-1', to_vault_id: 'vault-2' })
    )

    await expect(store.hail('vault-2')).resolves.toBe(true)

    expect(api.hail).toHaveBeenCalledWith('vault-1', 'vault-2')
    expect(store.awaitingTargets.has('vault-2')).toBe(true)
    expect(store.filings[0]?.filing_id).toBe('filing-1')
    expect(store.actionError).toBeNull()
  })

  it('surfaces the server reason when a hail is refused with 409', async () => {
    const store = useEnvoyStore()
    await store.start('vault-1')
    api.hail.mockRejectedValue(
      Object.assign(new Error('Conflict'), {
        name: 'ApiError',
        detail: 'You are already in contact with that vault.',
        status: 409,
      })
    )

    await expect(store.hail('vault-2')).resolves.toBe(false)

    expect(store.actionError).toBe('You are already in contact with that vault.')
    expect(store.acting).toBe(false)
  })

  it('answers a filing, drops it from the inbox and re-sweeps the roster', async () => {
    const store = useEnvoyStore()
    api.log.mockResolvedValue([filing({})])
    await store.start('vault-1')
    expect(store.pendingIncomingCount).toBe(1)

    api.respond.mockResolvedValue(
      filing({ status: 'ACCEPTED', responded_at: '2026-01-02T00:00:00Z' })
    )
    // The re-sweep is the authority; point it at the answered log.
    api.log.mockResolvedValue([filing({ status: 'ACCEPTED' })])
    await expect(store.respond('filing-1', true)).resolves.toBe(true)

    expect(api.respond).toHaveBeenCalledWith('vault-1', 'filing-1', true)
    expect(store.pendingIncomingCount).toBe(0)
    expect(store.filings[0]?.status).toBe('ACCEPTED')
    expect(api.signals).toHaveBeenCalledTimes(2)
  })

  it('keeps the last sweep on screen when a poll fails', async () => {
    const store = useEnvoyStore()
    await store.start('vault-1')
    api.signals.mockRejectedValue(new Error('band down'))

    await store.refresh()

    expect(store.signals).toHaveLength(4)
    expect(store.errorMessage).toBe('band down')
  })
})
