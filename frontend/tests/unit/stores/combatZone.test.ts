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

const fighter = {
  id: 'dweller-1',
  name: 'Test Dweller',
  level: 5,
  health: 100,
  max_health: 100,
  power: 42,
}

const match = {
  id: 'match-1',
  status: 'active',
  round_seq: 1,
  next_attack_party: 'A',
  pot_caps: 200,
  party_a: {
    fighter,
    party_id: 'party-1',
    vault_id: 'vault-1',
    vault_number: 101,
    dweller_id: 'dweller-1',
    stance: 'defensive',
    is_winner: false,
    credited_caps: null,
  },
  party_b: {
    fighter: { ...fighter, id: 'dweller-2', name: 'Other Dweller' },
    party_id: 'party-2',
    vault_id: 'vault-2',
    vault_number: 202,
    dweller_id: 'dweller-2',
    stance: 'defensive',
    is_winner: false,
    credited_caps: null,
  },
  events: [],
  cursor: { sequence: 0, round_seq: 1, status: 'active' },
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
    vi.mocked(combatZoneService.getHistory).mockResolvedValue([])
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

  it('ignores a late open response after the panel closes', async () => {
    let resolveLobby!: (value: CombatZoneLobbyRead) => void
    const pending = new Promise<CombatZoneLobbyRead>((resolve) => {
      resolveLobby = resolve
    })
    vi.mocked(combatZoneService.getLobby).mockReturnValueOnce(pending)
    vi.mocked(combatZoneService.getParty).mockResolvedValueOnce(null)

    const store = useCombatZoneStore()
    const opening = store.open('vault-1', 'token')
    store.close()
    resolveLobby(lobby)
    await opening

    expect(store.lobby).toBeNull()
    expect(store.party).toBeNull()
  })

  it('ignores an obsolete match response after switching matches', async () => {
    let resolveFirst!: (value: CombatZoneMatchRead) => void
    const firstPending = new Promise<CombatZoneMatchRead>((resolve) => {
      resolveFirst = resolve
    })
    const second = { ...match, id: 'match-2' } as CombatZoneMatchRead
    vi.mocked(combatZoneService.getMatch)
      .mockReturnValueOnce(firstPending)
      .mockResolvedValueOnce(second)

    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')
    const first = store.watchMatch('match-1')
    const switching = store.watchMatch('match-2')
    resolveFirst(match)
    await Promise.all([first, switching])

    expect(store.match?.id).toBe('match-2')
  })

  it('does not restore a challenge after the panel closes', async () => {
    let resolveChallenge!: (value: CombatZoneMatchRead) => void
    const pending = new Promise<CombatZoneMatchRead>((resolve) => {
      resolveChallenge = resolve
    })
    vi.mocked(combatZoneService.challenge).mockReturnValueOnce(pending)

    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')
    const challenge = store.challenge('party-2')
    store.close()
    resolveChallenge(match)

    expect(await challenge).toBe(false)
    expect(store.match).toBeNull()
  })

  it('rejects an older active snapshot after a newer finished result', async () => {
    let resolveActive!: (value: CombatZoneMatchRead) => void
    const activePending = new Promise<CombatZoneMatchRead>((resolve) => {
      resolveActive = resolve
    })
    const activeSnapshot = { ...match, id: 'match-1', status: 'active' } as CombatZoneMatchRead
    const finishedSnapshot = {
      ...match,
      id: 'match-1',
      status: 'finished',
      cursor: { sequence: 9, round_seq: 5, status: 'finished' },
    } as CombatZoneMatchRead
    vi.mocked(combatZoneService.getMatch)
      .mockReturnValueOnce(activePending)
      .mockResolvedValueOnce(finishedSnapshot)

    const store = useCombatZoneStore()
    await store.open('vault-1', 'token')
    store.activeMatchId = 'match-1'
    const older = store.refreshMatch()
    const newer = store.refreshMatch()
    await newer
    resolveActive(activeSnapshot)
    await older

    expect(store.match?.status).toBe('finished')
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
