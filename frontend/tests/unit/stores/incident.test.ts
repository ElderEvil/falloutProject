import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { incidentApi } from '@/modules/combat/api/incident'
import axios from '@/core/plugins/axios'
import type {
  IncidentListResponse,
  Incident,
  IncidentTeamMember,
} from '@/modules/combat/models/incident'
import { IncidentType, IncidentStatus } from '@/modules/combat/models/incident'

vi.mock('@/modules/combat/api/incident')
vi.mock('@/core/plugins/axios')
const sseMock = vi.hoisted(() => ({
  instance: null as any,
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  playSound: vi.fn(),
  startAlarm: vi.fn(),
  stopAlarm: vi.fn(),
  duckMusic: vi.fn(),
  restoreMusic: vi.fn(),
  cancelMusicRestore: vi.fn(),
}))

vi.mock('@/core/composables/useEventStream', () => ({ useSse: () => sseMock.instance }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => sseMock.toast }))
vi.mock('@/core/audio/audioManager', () => ({
  audioManager: {
    play: sseMock.playSound,
    startAlarmLoop: sseMock.startAlarm,
    stopAlarmLoop: sseMock.stopAlarm,
    duckMusic: sseMock.duckMusic,
    restoreMusic: sseMock.restoreMusic,
  },
}))

const mockIncident: Incident = {
  id: 'incident-1',
  vault_id: 'vault-1',
  room_id: 'room-1',
  room_name: 'Power Generator',
  type: IncidentType.RAIDER_ATTACK,
  status: IncidentStatus.ACTIVE,
  difficulty: 5,
  start_time: '2025-01-01T00:00:00Z',
  damage_dealt: 10,
  enemies_defeated: 2,
  spread_count: 0,
  rooms_affected: ['room-1'],
  last_spread_time: null,
  loot: null,
  unclaimed_loot: [],
  resolved_at: null,
  duration: 60,
  elapsed_time: 30,
  end_time: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  family: 'intrusion',
  objective: 'defeat',
  progress: { current: 30, target: 100, label: 'Threat' },
  risk: { kind: 'casualties', rooms_affected: 1 },
  response: { label: 'Send' },
  events: [],
}

const mockIncidentList: IncidentListResponse = {
  vault_id: 'vault-1',
  incident_count: 1,
  incidents: [
    {
      id: 'incident-1',
      type: IncidentType.RAIDER_ATTACK,
      status: IncidentStatus.ACTIVE,
      room_id: 'room-1',
      room_name: 'Power Generator',
      difficulty: 5,
      start_time: '2025-01-01T00:00:00Z',
      elapsed_time: 60,
      damage_dealt: 10,
      enemies_defeated: 2,
    },
  ],
}

const emptyList: IncidentListResponse = { vault_id: 'vault-1', incident_count: 0, incidents: [] }

const teamMember: IncidentTeamMember = {
  id: 'tm-1',
  team_id: 'team-1',
  dweller_id: 'dweller-1',
  slot_number: 1,
  status: 'assigned',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

/** Answer every poll with the active incident and its roster. */
const pollActive = (team?: IncidentTeamMember[]) => {
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
  vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)
  if (team) vi.mocked(incidentApi.getIncidentTeam).mockResolvedValue(team)
}

/** Answer just the next poll with the active incident. */
const pollActiveOnce = () => {
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
  vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
}

/** A full 40-line rolling journal window, optionally ending on a non-combat line. */
const journalWindow = (start: number, lastKind = 'hit') =>
  Array.from({ length: 40 }, (_, index) => ({
    id: `e${start + index}`,
    kind: index === 39 ? lastKind : 'hit',
    message: `Line ${start + index}`,
    data: null,
  }))

/** Queue `count` incident-detail requests that stay pending until released. */
function deferDetailResponses(count: number) {
  const resolvers: ((incident: Incident) => void)[] = []
  const detail = vi.mocked(incidentApi.getIncident)
  for (let i = 0; i < count; i += 1) {
    const pending = new Promise<Incident>((resolve) => resolvers.push(resolve))
    detail.mockImplementationOnce(() => pending)
  }
  return resolvers
}

/** An `incident_resolved` frame for the fixture incident. */
const resolvedEvent = (overrides: Record<string, unknown> = {}) => ({
  type: 'incident_resolved',
  incident_id: 'incident-1',
  success: true,
  ...overrides,
})

const resolveVictory = (caps_earned = 50) => resolveViaSse(resolvedEvent({ caps_earned }))
const resolveDefeat = () => resolveViaSse(resolvedEvent({ success: false }))

const storeWithIncident = () => {
  const seeded = useIncidentStore()
  seeded.incidents.set('incident-1', mockIncident)
  seeded.activeIncidentIds = ['incident-1']
  return seeded
}

/** Answer the next poll with an active incident and fetch it. */
const fetchActive = async () => {
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
  vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
  await useIncidentStore().fetchIncidents('vault-1', 'token')
}

/** The poll reports the incident gone; `getIncident` supplies the last record. */
const fetchResolved = async (detail: Incident | Error = mockIncident) => {
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(emptyList)
  if (detail instanceof Error) vi.mocked(incidentApi.getIncident).mockRejectedValueOnce(detail)
  else vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(detail)
  await storeWithIncident().fetchIncidents('vault-1', 'token')
  await flushPromises()
}

const startStream = async (detail: Incident = mockIncident) => {
  const store = storeWithIncident()
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
  vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(detail)
  store.startPolling('vault-1', 'token', 10_000)
  await Promise.resolve()
  return store
}

const deliver = async (data: Record<string, unknown>) => {
  sseMock.instance.event.value = { event: 'incident', data }
  await nextTick()
}

const resolveViaSse = async (data: Record<string, unknown>) => {
  // Deliver the frame before the initial poll reaches its bookkeeping, exactly as
  // a live stream would: `announcedResolutions` then filters the stale list.
  const store = storeWithIncident()
  vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
  vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
  store.startPolling('vault-1', 'token', 10_000)
  // Settle the initial poll first: an unresolved roster request would keep the store in its
  // bookkeeping phase and the stale-list filter would never be exercised.
  await flushPromises()
  await deliver(data)
  return store
}

/** Resolve an incident while an in-flight poll still lists it as active. */
const resolveAgainstStalePoll = async (data: Record<string, unknown>) => {
  const store = storeWithIncident()
  let finishPoll!: (list: IncidentListResponse) => void
  vi.mocked(incidentApi.getActiveIncidents).mockImplementationOnce(
    () => new Promise((resolve) => (finishPoll = resolve))
  )
  vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
  store.startPolling('vault-1', 'token', 10_000)
  await deliver(data)
  finishPoll(mockIncidentList)
  await flushPromises()
  return store
}

describe('Incident Store', () => {
  let store: ReturnType<typeof useIncidentStore>

  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
    sseMock.instance = {
      event: ref(null),
      status: ref<'idle' | 'connecting' | 'open' | 'closed'>('idle'),
      start: vi.fn(),
      close: vi.fn(),
      stopReconnect: vi.fn(),
    }
    store = useIncidentStore()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reports a held-item sale failure once', async () => {
    vi.mocked(incidentApi.sellOverflow).mockRejectedValueOnce(new Error('Sale unavailable'))
    await useIncidentStore().sellOverflow('vault-1', 'incident-1', 0, 'token')
    expect(sseMock.toast.error).toHaveBeenCalledTimes(1)
  })

  it('discovers a reserved rush incident without an SSE spawn event, then stops retrying', async () => {
    vi.mocked(incidentApi.getActiveIncidents)
      .mockResolvedValueOnce(emptyList)
      .mockResolvedValueOnce(emptyList)
      .mockResolvedValue({ ...mockIncidentList, incidents: [mockIncident] })
    vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)
    vi.mocked(incidentApi.getIncidentTeam).mockResolvedValue([])
    store.startPolling('vault-1', 'test-token')
    await flushPromises()
    store.watchPendingIncident('vault-1', 'incident-1', 'test-token')
    await vi.advanceTimersByTimeAsync(1000)
    expect(store.hasActiveIncidents).toBe(false)
    await vi.advanceTimersByTimeAsync(1000)
    expect(store.hasActiveIncidents).toBe(true)
    const calls = vi.mocked(incidentApi.getActiveIncidents).mock.calls.length
    await vi.advanceTimersByTimeAsync(3000)
    // The one-second discovery retry has stopped; the regular combat poll continues.
    expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(calls + 1)
    store.stopPolling()
  })

  it('initializes with empty state', () => {
    expect(store.incidents.size).toBe(0)
    expect(store.activeIncidentIds).toEqual([])
    expect(store.isPolling).toBe(false)
  })

  describe('Computed Properties', () => {
    it('activeIncidents should return list of incidents', () => {
      const store = storeWithIncident()

      expect(store.activeIncidents).toHaveLength(1)
      expect(store.activeIncidents[0]).toEqual(mockIncident)
    })

    it.each([
      [[], false],
      [['incident-1'], true],
    ])('hasActiveIncidents=%s for ids %j', (ids, expected) => {
      useIncidentStore().activeIncidentIds = ids as string[]

      expect(useIncidentStore().hasActiveIncidents).toBe(expected)
    })

    it('incidentCountByVault should count incidents per vault', () => {
      store.incidents.set('incident-1', mockIncident)
      store.incidents.set('incident-2', { ...mockIncident, id: 'incident-2', vault_id: 'vault-2' })
      store.activeIncidentIds = ['incident-1', 'incident-2']

      const counts = store.incidentCountByVault
      expect(counts['vault-1']).toBe(1)
      expect(counts['vault-2']).toBe(1)
    })
  })

  describe('fetchIncidents', () => {
    it('should fetch and store incidents', async () => {
      await fetchActive()

      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
    })

    it('refreshes dwellers when the stream announces a spawn', async () => {
      const filter = useDwellerFilterStore()
      pollActive([])
      store.startPolling('vault-1', 'token', 10_000)
      await vi.advanceTimersByTimeAsync(0)
      expect(filter.dwellers).toEqual([])
      vi.mocked(axios.get).mockResolvedValue({ data: [{ id: 'responder-1', first_name: 'Ada' }] })

      await deliver({ type: 'incident_spawned' })
      await vi.advanceTimersByTimeAsync(0)

      expect(filter.dwellers).toEqual([{ id: 'responder-1', first_name: 'Ada' }])
      store.stopPolling()
    })

    it.each([
      [
        'an empty list',
        () => vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(emptyList),
      ],
      [
        'an invalid response',
        () => vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(null as any),
      ],
      [
        'an API error',
        () =>
          vi
            .mocked(incidentApi.getActiveIncidents)
            .mockRejectedValueOnce(new Error('Network error')),
      ],
    ])('keeps no active incidents for %s', async (_label, arrange) => {
      arrange()

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual([])
    })

    it('keeps the last confirmed incident when a refresh fails', async () => {
      await fetchActive()

      vi.mocked(incidentApi.getActiveIncidents).mockRejectedValueOnce(new Error('Network error'))
      await useIncidentStore().fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
    })

    it('keeps a confirmed list when one incident detail refresh fails', async () => {
      const store = storeWithIncident()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 2,
        incidents: [
          mockIncidentList.incidents[0],
          { ...mockIncidentList.incidents[0], id: 'incident-2', room_id: 'room-2' },
        ],
      })
      vi.mocked(incidentApi.getIncident)
        .mockResolvedValueOnce(mockIncident)
        .mockRejectedValueOnce(new Error('Network error'))

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual(['incident-1', 'incident-2'])
    })
  })

  describe('assignResponders', () => {
    const roster = [{ id: 'dweller-2', first_name: 'Ada', last_name: 'Smith' }]

    beforeEach(() => {
      vi.mocked(axios.get).mockResolvedValue({ data: roster })
    })

    it('should refresh the incident after assigning a responder', async () => {
      vi.mocked(incidentApi.assignResponders).mockResolvedValueOnce({
        incident_id: 'incident-1',
        room_id: 'room-1',
        assigned_dweller_ids: ['dweller-1'],
      })
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        damage_dealt: 40,
      })
      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValueOnce([])

      await store.assignResponders('vault-1', 'incident-1', ['dweller-1'], 'token')

      expect(incidentApi.assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', [
        'dweller-1',
      ])
      expect(store.incidents.get('incident-1')?.damage_dealt).toBe(40)
      expect(useDwellerFilterStore().dwellers).toEqual(roster)
      expect(store.getIncidentTeam('incident-1')).toEqual([])
      expect(sseMock.toast.success).toHaveBeenCalledTimes(1)
    })

    it('warns when only part of the selected response team is accepted', async () => {
      useDwellerFilterStore().dwellers = roster as never
      vi.mocked(incidentApi.assignResponders).mockResolvedValueOnce({
        incident_id: 'incident-1',
        room_id: 'room-1',
        assigned_dweller_ids: ['dweller-1'],
      })
      pollActiveOnce()
      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValue([])

      await store.assignResponders('vault-1', 'incident-1', ['dweller-1', 'dweller-2'], 'token')

      expect(sseMock.toast.warning).toHaveBeenCalledWith(
        expect.stringContaining('1 of 2 responders assigned')
      )
      expect(sseMock.toast.warning).toHaveBeenCalledWith(expect.stringContaining('Ada Smith'))
      expect(sseMock.toast.success).not.toHaveBeenCalled()
    })

    it('should rethrow assignment failures without refreshing the incident', async () => {
      const store = storeWithIncident()
      vi.mocked(incidentApi.assignResponders).mockRejectedValueOnce(new Error('Assignment failed'))

      await expect(
        store.assignResponders('vault-1', 'incident-1', ['dweller-1'], 'token')
      ).rejects.toThrow('Assignment failed')

      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(useDwellerFilterStore().dwellers).toEqual([])
      expect(sseMock.toast.success).not.toHaveBeenCalled()
    })
  })

  describe('Incident teams', () => {
    it('fetchIncidentTeam loads and stores the team for the getter', async () => {
      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValueOnce([teamMember])

      await store.fetchIncidentTeam('vault-1', 'incident-1', 'token')

      expect(incidentApi.getIncidentTeam).toHaveBeenCalledWith('vault-1', 'incident-1')
      expect(store.getIncidentTeam('incident-1')).toEqual([teamMember])
    })

    it('returns an empty roster for an unknown incident', () => {
      expect(useIncidentStore().getIncidentTeam('missing')).toEqual([])
    })

    it('fetchIncidentTeam swallows failures without corrupting state', async () => {
      vi.mocked(incidentApi.getIncidentTeam).mockRejectedValueOnce(new Error('Network error'))

      await store.fetchIncidentTeam('vault-1', 'incident-1', 'token')

      expect(store.getIncidentTeam('incident-1')).toEqual([])
    })

    it('assignResponders posts the union roster and refreshes the team', async () => {
      const union = ['dweller-1', 'dweller-2']
      vi.mocked(incidentApi.assignResponders).mockResolvedValueOnce({
        incident_id: 'incident-1',
        room_id: 'room-1',
        assigned_dweller_ids: union,
      })
      pollActiveOnce()
      // The spawned-incident team fetch inside fetchIncidents and the explicit
      // refresh both read the roster, so the mock must answer every call.
      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValue([teamMember])

      await store.assignResponders('vault-1', 'incident-1', union, 'token')

      expect(incidentApi.assignResponders).toHaveBeenCalledWith('vault-1', 'incident-1', union)
      expect(incidentApi.getIncidentTeam).toHaveBeenCalledWith('vault-1', 'incident-1')
      expect(store.getIncidentTeam('incident-1')).toEqual([teamMember])
    })

    it('assignResponders failure leaves the team cache untouched', async () => {
      store.incidentTeams.set('incident-1', [teamMember])
      vi.mocked(incidentApi.assignResponders).mockRejectedValueOnce(new Error('Assignment failed'))

      await expect(
        store.assignResponders('vault-1', 'incident-1', ['dweller-2'], 'token')
      ).rejects.toThrow('Assignment failed')

      expect(incidentApi.getIncidentTeam).not.toHaveBeenCalled()
      expect(store.getIncidentTeam('incident-1')).toEqual([teamMember])
    })

    it('clears the team entry for incidents that vanish from the active list', async () => {
      const store = storeWithIncident()
      store.incidentTeams.set('incident-1', [teamMember])
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(emptyList)
      vi.mocked(incidentApi.getIncident).mockRejectedValueOnce(new Error('Incident not found'))

      await store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      expect(store.getIncidentTeam('incident-1')).toEqual([])
    })

    it('clearIncidents resets the team cache', () => {
      store.incidentTeams.set('incident-1', [teamMember])

      store.clearIncidents()

      expect(store.getIncidentTeam('incident-1')).toEqual([])
    })

    it('fetchIncidents loads the team for a newly spawned incident', async () => {
      pollActiveOnce()
      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValueOnce([teamMember])

      await useIncidentStore().fetchIncidents('vault-1', 'token')

      expect(incidentApi.getIncidentTeam).toHaveBeenCalledWith('vault-1', 'incident-1')
      expect(store.getIncidentTeam('incident-1')).toEqual([teamMember])
      expect(store.hasLoadedIncidentTeam('incident-1')).toBe(true)
    })

    it.each([[[teamMember]], [[]]])(
      'does not refetch a cached roster (%#) on later polls',
      async (team) => {
        vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
        vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)
        vi.mocked(incidentApi.getIncidentTeam).mockResolvedValue(team as never)

        await store.fetchIncidents('vault-1', 'token')
        expect(store.hasLoadedIncidentTeam('incident-1')).toBe(true)
        expect(incidentApi.getIncidentTeam).toHaveBeenCalledTimes(1)

        await store.fetchIncidents('vault-1', 'token')
        expect(incidentApi.getIncidentTeam).toHaveBeenCalledTimes(1)
      }
    )

    it('retries the team fetch on a later poll after a transient failure', async () => {
      pollActive()
      vi.mocked(incidentApi.getIncidentTeam)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce([teamMember])

      await store.fetchIncidents('vault-1', 'token')
      expect(store.hasLoadedIncidentTeam('incident-1')).toBe(false)

      await store.fetchIncidents('vault-1', 'token')
      expect(incidentApi.getIncidentTeam).toHaveBeenCalledTimes(2)
      expect(store.hasLoadedIncidentTeam('incident-1')).toBe(true)
      expect(store.getIncidentTeam('incident-1')).toEqual([teamMember])
    })

    it('hasLoadedIncidentTeam distinguishes loaded-empty from not-loaded', async () => {
      expect(store.hasLoadedIncidentTeam('incident-1')).toBe(false)

      vi.mocked(incidentApi.getIncidentTeam).mockResolvedValueOnce([])
      await store.fetchIncidentTeam('vault-1', 'incident-1', 'token')

      expect(store.hasLoadedIncidentTeam('incident-1')).toBe(true)
      expect(store.getIncidentTeam('incident-1')).toEqual([])
    })

    it('totalResponderCount sums the designated rosters of active incidents', () => {
      store.activeIncidentIds = ['incident-1', 'incident-2']
      store.incidentTeams.set('incident-1', [
        teamMember,
        { ...teamMember, id: 'tm-2', dweller_id: 'dweller-2' },
      ])
      store.incidentTeams.set('incident-2', [teamMember])

      expect(store.totalResponderCount).toBe(3)

      store.incidentTeams.clear()
      expect(store.totalResponderCount).toBe(0)
    })
  })

  it('rejects malformed lists for the scheduler without clearing active incidents', async () => {
    store.activeIncidentIds = ['existing-incident']
    vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue({} as never)

    await expect(store.fetchIncidents('vault-1', 'token', true)).rejects.toThrow(
      'Malformed incident list response'
    )
    expect(store.activeIncidentIds).toEqual(['existing-incident'])
  })

  describe('Polling', () => {
    it('uses the configured idle fallback cadence when SSE is disconnected', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(emptyList)
      store.startPolling('vault-1', 'token')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(9999)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(1)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(2)
      store.stopPolling()
    })

    it('refreshes active combat every two seconds and restores idle cadence after resolution', async () => {
      pollActive([])
      store.startPolling('vault-1', 'token')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(1999)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(1)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(2)

      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(emptyList)
      await vi.advanceTimersByTimeAsync(2000)
      expect(store.hasActiveIncidents).toBe(false)
      const calls = vi.mocked(incidentApi.getActiveIncidents).mock.calls.length
      await vi.advanceTimersByTimeAsync(9999)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(calls)
      await vi.advanceTimersByTimeAsync(1)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(calls + 1)
      store.stopPolling()
    })

    it('starts polling, fetches immediately and stops on demand', async () => {
      pollActive()

      store.startPolling('vault-1', 'token', 1000)
      expect(store.isPolling).toBe(true)

      await vi.advanceTimersByTimeAsync(1000)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(2) // Initial + 1 poll

      store.stopPolling()
      expect(store.isPolling).toBe(false)
    })

    it.each([
      ['a live incident', mockIncidentList, 1],
      ['nothing live', emptyList, 1],
    ])('handles an open stream with %s', async (_label, list, initialCalls) => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(list)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      store.startPolling('vault-1', 'token', 1000)
      sseMock.instance.status.value = 'open'
      await nextTick()
      await vi.advanceTimersByTimeAsync(1000)

      // A live incident must keep refreshing; with nothing live the stream alone is enough.
      if (list.incident_count > 0) {
        expect(incidentApi.getActiveIncidents.mock.calls.length).toBeGreaterThan(initialCalls)
      } else {
        expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(initialCalls)
      }
      store.stopPolling()
    })

    it('keeps polling when the stream closes', async () => {
      pollActive()

      store.startPolling('vault-1', 'token', 10000)
      sseMock.instance.status.value = 'open'
      await nextTick()
      sseMock.instance.status.value = 'closed'
      await nextTick()
      await vi.advanceTimersByTimeAsync(10000)

      expect(incidentApi.getActiveIncidents.mock.calls.length).toBeGreaterThan(1)
      store.stopPolling()
    })

    it('restarts polling when startPolling is called while already polling', async () => {
      pollActive()

      store.startPolling('vault-1', 'token', 1000)
      expect(store.isPolling).toBe(true)

      // A second call replaces the poller instead of leaving two intervals running.
      store.startPolling('vault-1', 'token', 1000)
      expect(store.isPolling).toBe(true)

      const callsAfterRestart = incidentApi.getActiveIncidents.mock.calls.length
      await vi.advanceTimersByTimeAsync(1000)

      expect(incidentApi.getActiveIncidents.mock.calls.length).toBe(callsAfterRestart + 1)
      store.stopPolling()
    })
  })

  describe('spawnDebugIncident', () => {
    it.each([
      [undefined, 'raider_attack', 5, 'Incident Spawned: raider attack (Difficulty: 5)'],
      ['fire', 'fire', 3, 'Incident Spawned: fire (Difficulty: 3)'],
    ])('spawns %s and refreshes the list', async (requested, type, difficulty, message) => {
      vi.mocked(incidentApi.spawnIncident).mockResolvedValueOnce({
        message: 'Incident spawned',
        incident_id: 'incident-1',
        type,
        room_id: 'room-1',
        difficulty,
      })
      pollActiveOnce()

      await store.spawnDebugIncident('vault-1', 'token', requested as never)

      if (requested) expect(incidentApi.spawnIncident).toHaveBeenCalledWith('vault-1', 'fire')
      expect(sseMock.toast.success).toHaveBeenCalledWith(message)
      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
    })

    it('should handle spawn failure', async () => {
      vi.mocked(incidentApi.spawnIncident).mockRejectedValueOnce(new Error('Spawn failed'))

      await expect(store.spawnDebugIncident('vault-1', 'token')).rejects.toThrow()

      expect(store.incidents.size).toBe(0)
      expect(store.activeIncidentIds).toEqual([])
      expect(sseMock.toast.success).not.toHaveBeenCalled()
      expect(sseMock.toast.error).toHaveBeenCalledTimes(1)
    })
  })

  describe('Utility Methods', () => {
    it('clearIncidents should reset state', () => {
      const store = storeWithIncident()

      store.clearIncidents()

      expect(store.incidents.size).toBe(0)
      expect(store.activeIncidentIds).toEqual([])
    })

    it.each([
      ['incident-1', mockIncident],
      ['non-existent', undefined],
    ])('getIncidentById(%s) returns the record or undefined', (id, expected) => {
      store.incidents.set('incident-1', mockIncident)

      expect(store.getIncidentById(id)).toEqual(expected)
    })
  })

  describe('Multiple Incident Handling', () => {
    it('should handle multiple incidents correctly', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 2,
        incidents: [
          mockIncidentList.incidents[0],
          {
            ...mockIncidentList.incidents[0],
            id: 'incident-2',
            type: IncidentType.FIRE,
            status: IncidentStatus.SPREADING,
            room_id: 'room-2',
          },
        ],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toHaveLength(2)
      expect(store.activeIncidentIds).toEqual(['incident-1', 'incident-2'])
    })

    it('should detect resolved incidents and remove them', async () => {
      store.activeIncidentIds = ['incident-1', 'incident-2']

      // Now only incident-1 is active
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual(['incident-1'])
    })
  })

  describe('Aftermath', () => {
    it('retains the final structured journal for scene playback', async () => {
      const final = {
        ...mockIncident,
        status: IncidentStatus.RESOLVED,
        events: [
          {
            id: 'final',
            kind: 'hit',
            message: 'Final hit',
            data: null,
            action: { actor_id: 'd1', targets: [{ target_id: 'threat', damage: 1 }] },
          },
        ],
      }

      await fetchResolved(final)

      expect(store.aftermathForRoom('room-1')?.scene).toEqual(final)
      expect(store.aftermathForRoom('room-1')?.sceneLoading).toBe(false)
      expect(store.activeIncidents).toEqual([])
    })

    it('discards an old final-journal response after clearing the account', async () => {
      const store = storeWithIncident()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(emptyList)
      let finish!: (incident: Incident) => void
      vi.mocked(incidentApi.getIncident).mockImplementationOnce(
        () => new Promise((resolve) => (finish = resolve))
      )

      await store.fetchIncidents('vault-1', 'token')
      expect(store.aftermathForRoom('room-1')?.sceneLoading).toBe(true)

      store.clearIncidents()
      finish({ ...mockIncident, status: IncidentStatus.RESOLVED })
      await flushPromises()

      expect(store.aftermaths.size).toBe(0)
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentVictory', 'sfx')
    })

    it('summarises a victory with the caps it recovered', async () => {
      const store = await resolveVictory()

      expect(store.aftermathForRoom('room-1')).toMatchObject({
        incidentId: 'incident-1',
        roomId: 'room-1',
        roomName: 'Power Generator',
        outcome: 'victory',
        capsEarned: 50,
        damageDealt: 10,
        enemiesDefeated: 2,
        rounds: 0,
      })
      store.stopPolling()
    })

    it('skips the global cue when the open scene owns the resolution', async () => {
      const marker = document.createElement('div')
      marker.dataset.incidentSceneId = 'incident-1'
      document.body.appendChild(marker)
      sseMock.playSound.mockClear()

      try {
        await resolveViaSse(resolvedEvent())
        expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentVictory', 'sfx')
      } finally {
        marker.remove()
      }
    })

    it('summarises a defeat so the room shows what was lost', async () => {
      const store = await resolveDefeat()

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'defeat', capsEarned: 0 })
      store.stopPolling()
    })

    it('keeps the summary when the resolution frame is re-delivered', async () => {
      const store = await resolveVictory()

      await deliver(resolvedEvent({ caps_earned: 50 }))

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'victory', capsEarned: 50 })
      store.stopPolling()
    })

    it('announces a hazard victory without promising caps', async () => {
      const store = await resolveVictory(0)

      expect(sseMock.toast.success).toHaveBeenCalledWith(
        'Incident resolved — responders earned experience.'
      )
      store.stopPolling()
    })

    it('records an unknown outcome when only the poll sees the incident end', async () => {
      await fetchResolved(new Error('Incident not found'))

      expect(useIncidentStore().aftermathForRoom('room-1')).toMatchObject({
        incidentId: 'incident-1',
        outcome: 'unknown',
        capsEarned: 0,
        roomName: 'Power Generator',
      })
    })

    it('reconciles a missed resolution from the incident record', async () => {
      await fetchResolved({
        ...mockIncident,
        status: IncidentStatus.RESOLVED,
        loot: { caps: 35, items: [] },
      } as Incident)

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'victory', capsEarned: 35 })
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentVictory', 'sfx')
    })

    it('reconciles a missed failure from the incident record', async () => {
      await fetchResolved({ ...mockIncident, status: IncidentStatus.FAILED, loot: null })

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'defeat', capsEarned: 0 })
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentDefeat', 'sfx')
    })

    it('reports the experience a resolved incident paid', async () => {
      await fetchResolved({
        ...mockIncident,
        status: IncidentStatus.RESOLVED,
        loot: { caps: 0, experience: 45, items: [] },
      } as Incident)

      expect(useIncidentStore().aftermathForRoom('room-1')).toMatchObject({
        outcome: 'victory',
        experienceEarned: 45,
      })
    })

    it('invents no aftermath when an incident is merely first seen', async () => {
      await fetchActive()

      expect(useIncidentStore().aftermathForRoom('room-1')).toBeUndefined()
    })

    it.each([
      [
        'clearAftermath',
        (store: ReturnType<typeof useIncidentStore>) => store.clearAftermath('room-1'),
      ],
      ['clearIncidents', (store: ReturnType<typeof useIncidentStore>) => store.clearIncidents()],
    ])('%s drops the summary', async (_label, dismiss) => {
      const store = await resolveViaSse(resolvedEvent())

      dismiss(store)

      expect(store.aftermathForRoom('room-1')).toBeUndefined()
      store.stopPolling()
    })
  })

  describe('Spawn alert', () => {
    it('loops the alarm and ducks the music when an incident spawns', async () => {
      pollActiveOnce()

      await useIncidentStore().fetchIncidents('vault-1', 'token')
      await nextTick()

      expect(sseMock.startAlarm).toHaveBeenCalled()
      expect(sseMock.duckMusic).toHaveBeenCalled()
    })

    it('stops the alarm and restores the music when the chain ends', async () => {
      store.activeIncidentIds = ['incident-1']
      await nextTick()
      sseMock.startAlarm.mockClear()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({ incidents: [] })

      await store.fetchIncidents('vault-1', 'token')
      await nextTick()

      expect(sseMock.startAlarm).not.toHaveBeenCalled()
      expect(sseMock.stopAlarm).toHaveBeenCalled()
      expect(sseMock.restoreMusic).toHaveBeenCalled()
    })
  })

  describe('Combat SFX', () => {
    it('plays the per-incident spawn sound once per incident id', async () => {
      pollActive()

      await store.fetchIncidents('vault-1', 'token')
      await store.fetchIncidents('vault-1', 'token')

      expect(sseMock.playSound).toHaveBeenCalledWith('incidentRaider', 'sfx')
      const raiderCalls = sseMock.playSound.mock.calls.filter(([key]) => key === 'incidentRaider')
      expect(raiderCalls).toHaveLength(1)
    })

    it('maps each incident type to its own spawn sound', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        ...mockIncidentList,
        incidents: [
          { ...mockIncidentList.incidents[0], id: 'incident-2', type: IncidentType.FIRE },
        ],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        id: 'incident-2',
        type: IncidentType.FIRE,
      })

      await useIncidentStore().fetchIncidents('vault-1', 'token')

      expect(sseMock.playSound).toHaveBeenCalledWith('incidentFire', 'sfx')
    })

    it('refreshes the vault controls when a spawn automatically pauses it', async () => {
      const refresh = vi.spyOn(useVaultStore(), 'fetchGameState').mockResolvedValue(undefined)
      pollActive()
      store.startPolling('vault-1', 'token', 10_000)

      await deliver({ type: 'incident_spawned', is_paused: true })
      await flushPromises()

      expect(refresh).toHaveBeenCalledWith('vault-1')
      store.stopPolling()
    })

    it('does not double-play the spawn sound when SSE and poll both see the incident', async () => {
      pollActive()
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      await deliver({
        type: 'incident_spawned',
        incident_id: 'incident-1',
        incident_type: 'raider_attack',
      })
      await flushPromises()
      await store.fetchIncidents('vault-1', 'token')

      const raiderCalls = sseMock.playSound.mock.calls.filter(([key]) => key === 'incidentRaider')
      expect(raiderCalls).toHaveLength(1)
      store.stopPolling()
    })

    it('plays the defeat sound when an incident is lost', async () => {
      const store = await startStream()

      await deliver({ type: 'incident_resolved', incident_id: 'incident-1', success: false })

      expect(sseMock.playSound).toHaveBeenCalledWith('incidentDefeat', 'sfx')
      store.stopPolling()
    })

    it('plays a hit sound on a new round but not on first sight', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident)
        .mockResolvedValueOnce(mockIncident)
        .mockResolvedValueOnce({
          ...mockIncident,
          events: [{ id: 'e1', kind: 'round', message: 'Round 1', data: null }],
        })

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentHit', 'sfx')
    })

    it('does not replay the hit sound or lower the count when a stale response resolves late', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      const round1 = { id: 'e1', kind: 'round', message: 'Round 1', data: null }
      const round2 = { id: 'e2', kind: 'round', message: 'Round 2', data: null }

      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        events: [round1],
      })
      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      // Two overlapping polls race; the stale (1-event) response resolves after the fresh (2-event) one.
      const [resolveFresh, resolveStale] = deferDetailResponses(2)

      const pollA = store.fetchIncidents('vault-1', 'token')
      const pollB = store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      resolveFresh({ ...mockIncident, events: [round1, round2] })
      await flushPromises()
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentHit', 'sfx')
      sseMock.playSound.mockClear()

      resolveStale({ ...mockIncident, events: [round1] })
      await flushPromises()
      await Promise.all([pollA, pollB])
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      // The count was never lowered, so a later fresh response must not replay the hit.
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        events: [round1, round2],
      })
      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')
    })

    it('keeps the hit sound for combat lines but not for an assignment in the full window', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident)
        .mockResolvedValueOnce({ ...mockIncident, events: journalWindow(1) })
        .mockResolvedValueOnce({ ...mockIncident, events: journalWindow(2, 'responders_assigned') })
        .mockResolvedValueOnce({ ...mockIncident, events: journalWindow(3) })

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentHit', 'sfx')
    })

    it('rejects an older full journal window that resolves after a newer one', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)

      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        events: journalWindow(1),
      })
      await store.fetchIncidents('vault-1', 'token')

      const [resolveOlder, resolveNewer] = deferDetailResponses(2)

      const olderPoll = store.fetchIncidents('vault-1', 'token')
      const newerPoll = store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      resolveNewer({ ...mockIncident, events: journalWindow(2) })
      await flushPromises()
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentHit', 'sfx')
      sseMock.playSound.mockClear()

      resolveOlder({ ...mockIncident, events: journalWindow(1) })
      await flushPromises()
      await Promise.all([olderPoll, newerPoll])

      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')
      expect(store.incidents.get('incident-1')?.events.at(-1)?.id).toBe('e41')
    })

    it('still plays the hit sound when the rolling journal window is full', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident)
        .mockResolvedValueOnce({ ...mockIncident, events: journalWindow(1) })
        .mockResolvedValueOnce({ ...mockIncident, events: journalWindow(2) })

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).not.toHaveBeenCalledWith('incidentHit', 'sfx')

      await store.fetchIncidents('vault-1', 'token')
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentHit', 'sfx')
    })
  })

  describe('SSE notifications', () => {
    it('announces a successful incident resolution', async () => {
      const store = await resolveAgainstStalePoll(resolvedEvent({ caps_earned: 50 }))

      expect(store.activeIncidentIds).toEqual([])
      expect(sseMock.toast.success).toHaveBeenCalledWith('Incident victory — recovered 50 caps.')
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentVictory', 'sfx')
      store.stopPolling()
    })

    it('announces the experience a zero-caps victory paid', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
        caps_earned: 0,
        experience_earned: 45,
      })

      expect(store.aftermathForRoom('room-1')).toMatchObject({ experienceEarned: 45 })
      expect(sseMock.toast.success).toHaveBeenCalledWith(
        'Incident victory — responders earned 45 XP.'
      )
      store.stopPolling()
    })

    it('announces a lost incident so a failure is never silent', async () => {
      const store = await resolveAgainstStalePoll(resolvedEvent({ success: false }))

      expect(store.activeIncidentIds).toEqual([])
      expect(sseMock.toast.error).toHaveBeenCalledWith(
        `Incident lost — ${mockIncident.type.replace(/_/g, ' ')} overran ${mockIncident.room_name}.`
      )
      expect(sseMock.playSound).toHaveBeenCalledWith('incidentDefeat', 'sfx')
      store.stopPolling()
    })

    it('announces a lost incident even when its details were already dropped', async () => {
      store.activeIncidentIds = ['incident-9']
      pollActive()
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      await deliver({ type: 'incident_resolved', incident_id: 'incident-9', success: false })

      expect(sseMock.toast.error).toHaveBeenCalledWith(
        'Incident lost — the threat was not contained.'
      )
      store.stopPolling()
    })

    it.each([
      [true, 50, 'success'],
      [false, 0, 'error'],
    ] as const)(
      'announces a resolution (success=%s) only once when the event is re-delivered',
      async (success, capsEarned, channel) => {
        const store = await startStream()

        const event = {
          type: 'incident_resolved',
          incident_id: 'incident-1',
          success,
          caps_earned: capsEarned,
        }
        await deliver(event)
        await deliver(event)

        expect(sseMock.toast[channel]).toHaveBeenCalledTimes(1)
        store.stopPolling()
      }
    )
  })

  describe('Overflow claims', () => {
    const heldLoot = [{ item_type: 'weapon', rarity: 'common', name: 'Raider Pistol' }]
    const resolved = { type: 'incident_resolved', incident_id: 'incident-1', success: true }

    it('reloads held loot once the incident is resolved', async () => {
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      // The detail refresh and the aftermath reload both fetch the incident, and
      // either may run first, so every answer carries the held loot.
      vi.mocked(incidentApi.getIncident).mockResolvedValue({
        ...mockIncident,
        unclaimed_loot: heldLoot,
      })
      const store = storeWithIncident()
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      await deliver(resolved)
      await flushPromises()

      expect(store.aftermathForRoom('room-1')?.unclaimed).toEqual(heldLoot)
      store.stopPolling()
    })

    it('stores a held item and updates the aftermath', async () => {
      const store = await resolveViaSse(resolved)
      vi.mocked(incidentApi.takeOverflow).mockResolvedValueOnce({
        caps_granted: 0,
        unclaimed_loot: [],
      })

      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')

      expect(incidentApi.takeOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0)
      expect(store.aftermathForRoom('room-1')?.unclaimed).toEqual([])
      store.stopPolling()
    })

    it('sells a held item for its caps', async () => {
      const store = await resolveViaSse(resolved)
      vi.mocked(incidentApi.sellOverflow).mockResolvedValueOnce({
        caps_granted: 12,
        unclaimed_loot: [],
      })

      await store.sellOverflow('vault-1', 'incident-1', 0, 'token')

      expect(incidentApi.sellOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0)
      expect(sseMock.toast.success).toHaveBeenCalledWith('Sold for 12 caps.')
      store.stopPolling()
    })

    it('only blames storage when the take fails with 409', async () => {
      const store = await resolveViaSse(resolved)

      vi.mocked(incidentApi.takeOverflow).mockRejectedValueOnce({ response: { status: 409 } })
      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')
      expect(sseMock.toast.error).toHaveBeenCalledTimes(1)
      expect(sseMock.toast.error).toHaveBeenCalledWith(
        'Storage is full — sell the item or free a slot.'
      )

      sseMock.toast.error.mockClear()
      vi.mocked(incidentApi.takeOverflow).mockRejectedValueOnce({ response: { status: 500 } })
      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')
      expect(sseMock.toast.error).toHaveBeenCalledTimes(1)
      expect(sseMock.toast.error).toHaveBeenCalledWith('Could not store the held item.')
      expect(sseMock.toast.error).not.toHaveBeenCalledWith(
        'Storage is full — sell the item or free a slot.'
      )
      store.stopPolling()
    })
  })
})
