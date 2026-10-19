import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createToastMock } from '../helpers/mocks'
import { useCombatZoneStore } from '@/modules/combat-zone/stores/combatZone'
import * as combatZoneService from '@/modules/combat-zone/api/combatZoneService'
import type {
  CombatZoneLobbyRead,
  CombatZoneMatchRead,
  CombatZonePartyRead,
} from '@/modules/combat-zone/models/combatZone'

vi.mock('@/modules/combat-zone/api/combatZoneService')

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

const lobby: CombatZoneLobbyRead = {
  enabled: true,
  server_time: '2026-10-19T18:00:00Z',
  entry_fee_caps: 100,
  travel_seconds: 60,
  queued: [],
  active_matches: [],
}

const party: CombatZonePartyRead = {
  id: 'party-1',
  vault_id: 'vault-1',
  vault_number: 101,
  dweller_id: 'dweller-1',
  dweller_name: 'Test Dweller',
  level: 5,
  health: 100,
  max_health: 100,
  power: 42,
  status: 'traveling',
  stance: 'defensive',
  arrives_at: null,
  escrow_caps: 100,
}

const match = {
  id: 'match-1',
  status: 'active',
  round_seq: 1,
  next_attack_party: 'A',
  pot_caps: 200,
  party_a: { ...party, party_id: 'party-1' },
  party_b: { ...party, party_id: 'party-2', vault_number: 202 },
  events: [],
} as unknown as CombatZoneMatchRead

describe('Combat Zone store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(combatZoneService.getLobby).mockResolvedValue(lobby)
    vi.mocked(combatZoneService.getParty).mockResolvedValue(null)
    vi.mocked(combatZoneService.sendParty).mockResolvedValue(party)
    vi.mocked(combatZoneService.recallParty).mockResolvedValue({ ...party, status: 'returning' })
    vi.mocked(combatZoneService.setStance).mockResolvedValue({ ...party, stance: 'focus' })
    vi.mocked(combatZoneService.challenge).mockResolvedValue(match)
    vi.mocked(combatZoneService.getMatch).mockResolvedValue(match)
    vi.mocked(combatZoneService.setVaultEnabled).mockResolvedValue({
      vault_id: 'vault-1',
      enabled: false,
    })
  })

  it('loads the lobby and party when opened', async () => {
    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')

    expect(store.lobby).toEqual(lobby)
    expect(store.party).toBeNull()
    expect(combatZoneService.getLobby).toHaveBeenCalledWith('token')
    expect(combatZoneService.getParty).toHaveBeenCalledWith('token', 'vault-1')
  })

  it('sends a contender and refreshes the party', async () => {
    vi.mocked(combatZoneService.getParty).mockResolvedValueOnce(null).mockResolvedValue(party)
    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')

    expect(await store.sendParty('dweller-1')).toBe(true)
    expect(combatZoneService.sendParty).toHaveBeenCalledWith('token', 'vault-1', 'dweller-1')
    expect(store.party).toEqual(party)
  })

  it('opens a challenge match and returns to the lobby', async () => {
    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')

    expect(await store.challenge('party-2')).toBe(true)
    expect(store.match?.id).toBe('match-1')
    expect(store.activeMatchId).toBe('match-1')

    store.backToLobby()
    expect(store.match).toBeNull()
    expect(store.activeMatchId).toBeNull()
  })

  it('toggles the per-vault admin switch', async () => {
    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')

    expect(await store.setVaultEnabled('vault-1', 'token', false)).toBe(true)
    expect(combatZoneService.setVaultEnabled).toHaveBeenCalledWith('token', 'vault-1', false)
  })

  it('sets a stance and keeps the party in sync', async () => {
    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')
    await store.sendParty('dweller-1')

    await store.setStance('focus')
    expect(combatZoneService.setStance).toHaveBeenCalledWith('token', 'vault-1', 'focus')
    expect(store.party?.stance).toBe('focus')
  })
})
