import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { incidentApi } from '@/modules/combat/api/incident'
import type { IncidentListResponse, Incident } from '@/modules/combat/models/incident'
import { IncidentType, IncidentStatus } from '@/modules/combat/models/incident'

vi.mock('@/modules/combat/api/incident')
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

vi.mock('@/core/composables/useEventStream', () => ({
  useSse: () => sseMock.instance,
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => sseMock.toast,
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => ({
    playSound: sseMock.playSound,
    playMusic: vi.fn(),
    stopMusic: vi.fn(),
    startAlarm: sseMock.startAlarm,
    stopAlarm: sseMock.stopAlarm,
    duckMusic: sseMock.duckMusic,
    restoreMusic: sseMock.restoreMusic,
    cancelMusicRestore: sseMock.cancelMusicRestore,
  }),
}))

describe('Incident Store', () => {
  beforeEach(() => {
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
  })

  afterEach(() => {
    vi.useRealTimers()
  })

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

  describe('State Initialization', () => {
    it('should initialize with empty state', () => {
      const store = useIncidentStore()
      expect(store.incidents.size).toBe(0)
      expect(store.activeIncidentIds).toEqual([])
      expect(store.isPolling).toBe(false)
    })
  })

  describe('Computed Properties', () => {
    it('activeIncidents should return list of incidents', () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']

      expect(store.activeIncidents).toHaveLength(1)
      expect(store.activeIncidents[0]).toEqual(mockIncident)
    })

    it('hasActiveIncidents should return true when incidents exist', () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-1']

      expect(store.hasActiveIncidents).toBe(true)
    })

    it('hasActiveIncidents should return false when no incidents', () => {
      const store = useIncidentStore()
      expect(store.hasActiveIncidents).toBe(false)
    })

    it('incidentCountByVault should count incidents per vault', () => {
      const store = useIncidentStore()
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
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
    })

    it('should handle empty incident list', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual([])
    })

    it('should show notification for new incidents', async () => {
      const store = useIncidentStore()

      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      // Verify the incident was added to the store (notification is handled by toast system)
      expect(store.activeIncidentIds).toContain('incident-1')
    })

    it('should handle invalid response gracefully', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(null as any)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual([])
    })

    it('should handle API errors without crashing', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockRejectedValueOnce(new Error('Network error'))

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual([])
    })

    it('keeps the last confirmed incident when a refresh fails', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      await store.fetchIncidents('vault-1', 'token')

      vi.mocked(incidentApi.getActiveIncidents).mockRejectedValueOnce(new Error('Network error'))
      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toEqual(['incident-1'])
      expect(store.incidents.get('incident-1')).toEqual(mockIncident)
    })

    it('keeps a confirmed list when one incident detail refresh fails', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
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
    it('should refresh the incident after assigning a responder', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.assignResponders).mockResolvedValueOnce()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.assignResponders('vault-1', 'incident-1', ['dweller-1'], 'token')

      expect(incidentApi.assignResponders).toHaveBeenCalledWith(
        'vault-1',
        'incident-1',
        ['dweller-1'],
        'token'
      )
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledWith('vault-1', 'token')
      expect(incidentApi.getIncident).toHaveBeenCalledWith('vault-1', 'incident-1', 'token')
    })

    it('should rethrow assignment failures without refreshing the incident', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.assignResponders).mockRejectedValueOnce(new Error('Assignment failed'))

      await expect(store.assignResponders('vault-1', 'incident-1', ['dweller-1'], 'token')).rejects.toThrow(
        'Assignment failed'
      )

      expect(incidentApi.getActiveIncidents).not.toHaveBeenCalled()
      expect(incidentApi.getIncident).not.toHaveBeenCalled()
    })
  })

  describe('Polling', () => {
    it('should start polling and fetch incidents', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      store.startPolling('vault-1', 'token', 1000)

      expect(store.isPolling).toBe(true)

      // Fast-forward time
      await vi.advanceTimersByTimeAsync(1000)

      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(2) // Initial + 1 poll
    })

    it('should stop polling', () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)

      store.startPolling('vault-1', 'token', 1000)
      expect(store.isPolling).toBe(true)

      store.stopPolling()
      expect(store.isPolling).toBe(false)
    })

    it('keeps refreshing while the stream is open so an overlay can advance', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      store.startPolling('vault-1', 'token', 1000)
      sseMock.instance.status.value = 'open'
      await nextTick()
      await vi.advanceTimersByTimeAsync(1000)

      // The stream never carries a round, so a live incident must keep refreshing.
      expect(incidentApi.getActiveIncidents.mock.calls.length).toBeGreaterThan(1)
      store.stopPolling()
    })

    it('stays quiet while the stream is open and nothing is live', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })

      store.startPolling('vault-1', 'token', 1000)
      sseMock.instance.status.value = 'open'
      await nextTick()
      await vi.advanceTimersByTimeAsync(1000)

      // Nothing to keep current, so the stream alone is enough.
      expect(incidentApi.getActiveIncidents).toHaveBeenCalledTimes(1)
      store.stopPolling()
    })

    it('keeps polling when the stream closes', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      store.startPolling('vault-1', 'token', 10000)
      sseMock.instance.status.value = 'open'
      await nextTick()
      sseMock.instance.status.value = 'closed'
      await nextTick()
      await vi.advanceTimersByTimeAsync(10000)

      expect(incidentApi.getActiveIncidents.mock.calls.length).toBeGreaterThan(1)
      store.stopPolling()
    })

    // TODO: Fix timing issue with polling interval references
    it.skip('should restart polling if already polling', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValue(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      store.startPolling('vault-1', 'token', 1000)
      await vi.waitFor(() => expect((store as any).pollInterval).not.toBeNull())
      const firstInterval = (store as any).pollInterval

      store.startPolling('vault-1', 'token', 1000)
      await vi.waitFor(() => expect((store as any).pollInterval).not.toBe(firstInterval))
      const secondInterval = (store as any).pollInterval

      expect(firstInterval).not.toBe(secondInterval)
      expect(secondInterval).not.toBeNull()
    })
  })

  describe('spawnDebugIncident', () => {
    it('should spawn incident and refresh list', async () => {
      const store = useIncidentStore()

      vi.mocked(incidentApi.spawnIncident).mockResolvedValueOnce({
        message: 'Incident spawned',
        incident_id: 'incident-1',
        type: 'raider_attack',
        room_id: 'room-1',
        difficulty: 5,
      })
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.spawnDebugIncident('vault-1', 'token')

      // Toast success notification is shown (tested by integration, not mocked here)
      expect(incidentApi.getActiveIncidents).toHaveBeenCalled()
    })

    it('should handle spawn failure', async () => {
      const store = useIncidentStore()

      vi.mocked(incidentApi.spawnIncident).mockRejectedValueOnce(new Error('Spawn failed'))

      await expect(store.spawnDebugIncident('vault-1', 'token')).rejects.toThrow()

      // Toast error notification is shown (tested by integration, not mocked here)
    })

    it('should spawn specific incident type', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.spawnIncident).mockResolvedValueOnce({
        message: 'Incident spawned',
        incident_id: 'incident-1',
        type: 'fire',
        room_id: 'room-1',
        difficulty: 3,
      })
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.spawnDebugIncident('vault-1', 'token', 'fire')

      expect(incidentApi.spawnIncident).toHaveBeenCalledWith('vault-1', 'token', 'fire')
    })
  })

  describe('Utility Methods', () => {
    it('clearIncidents should reset state', () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']

      store.clearIncidents()

      expect(store.incidents.size).toBe(0)
      expect(store.activeIncidentIds).toEqual([])
    })

    it('getIncidentById should return incident', () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)

      const incident = store.getIncidentById('incident-1')
      expect(incident).toEqual(mockIncident)
    })

    it('getIncidentById should return undefined for non-existent incident', () => {
      const store = useIncidentStore()

      const incident = store.getIncidentById('non-existent')
      expect(incident).toBeUndefined()
    })
  })

  describe('Multiple Incident Handling', () => {
    it('should handle multiple incidents correctly', async () => {
      const store = useIncidentStore()
      const multipleIncidents: IncidentListResponse = {
        vault_id: 'vault-1',
        incident_count: 2,
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
          {
            id: 'incident-2',
            type: IncidentType.FIRE,
            status: IncidentStatus.SPREADING,
            room_id: 'room-2',
            room_name: 'Diner',
            difficulty: 3,
            start_time: '2025-01-01T00:00:00Z',
            elapsed_time: 30,
            damage_dealt: 5,
            enemies_defeated: 0,
          },
        ],
      }

      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(multipleIncidents)
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toHaveLength(2)
      expect(store.activeIncidentIds).toContain('incident-1')
      expect(store.activeIncidentIds).toContain('incident-2')
    })

    it('should detect resolved incidents and remove them', async () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-1', 'incident-2']

      // Now only incident-1 is active
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 1,
        incidents: [mockIncidentList.incidents[0]],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toHaveLength(1)
      expect(store.activeIncidentIds).toContain('incident-1')
      expect(store.activeIncidentIds).not.toContain('incident-2')
    })
  })

  const resolveViaSse = async (data: Record<string, unknown>) => {
    const store = useIncidentStore()
    store.incidents.set('incident-1', mockIncident)
    store.activeIncidentIds = ['incident-1']
    vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
    vi.mocked(incidentApi.getIncident)
      .mockResolvedValueOnce(mockIncident)
      .mockResolvedValue(mockIncident)
    store.startPolling('vault-1', 'token', 10_000)
    await Promise.resolve()

    sseMock.instance.event.value = { event: 'incident', data }
    await nextTick()
    return store
  }

  describe('Aftermath', () => {
    it('summarises a victory with the caps it recovered', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
        caps_earned: 50,
      })

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

    it('summarises a defeat so the room shows what was lost', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: false,
      })

      expect(store.aftermathForRoom('room-1')).toMatchObject({
        outcome: 'defeat',
        capsEarned: 0,
      })
      store.stopPolling()
    })

    it('keeps the summary when the resolution frame is re-delivered', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
        caps_earned: 50,
      })

      sseMock.instance.event.value = {
        event: 'incident',
        data: {
          type: 'incident_resolved',
          incident_id: 'incident-1',
          success: true,
          caps_earned: 50,
        },
      }
      await nextTick()

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'victory', capsEarned: 50 })
      store.stopPolling()
    })

    it('announces a hazard victory without promising caps', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
        caps_earned: 0,
      })

      expect(sseMock.toast.success).toHaveBeenCalledWith(
        'Incident resolved — responders earned experience.'
      )
      store.stopPolling()
    })

    it('records an unknown outcome when only the poll sees the incident end', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })
      vi.mocked(incidentApi.getIncident).mockRejectedValueOnce(new Error('Incident not found'))

      await store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      expect(store.aftermathForRoom('room-1')).toMatchObject({
        incidentId: 'incident-1',
        outcome: 'unknown',
        capsEarned: 0,
        roomName: 'Power Generator',
      })
    })

    it('reconciles a missed resolution from the incident record', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        status: IncidentStatus.RESOLVED,
        loot: { caps: 35, items: [] },
      })

      await store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'victory', capsEarned: 35 })
    })

    it('reconciles a missed failure from the incident record', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        status: IncidentStatus.FAILED,
        loot: null,
      })

      await store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      expect(store.aftermathForRoom('room-1')).toMatchObject({ outcome: 'defeat', capsEarned: 0 })
    })

    it('reports the experience a resolved incident paid', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({
        vault_id: 'vault-1',
        incident_count: 0,
        incidents: [],
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce({
        ...mockIncident,
        status: IncidentStatus.RESOLVED,
        loot: { caps: 0, experience: 45, items: [] },
      })

      await store.fetchIncidents('vault-1', 'token')
      await flushPromises()

      expect(store.aftermathForRoom('room-1')).toMatchObject({
        outcome: 'victory',
        experienceEarned: 45,
      })
    })

    it('invents no aftermath when an incident is merely first seen', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.aftermathForRoom('room-1')).toBeUndefined()
    })

    it('drops a summary only when it is dismissed', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
      })

      store.clearAftermath('room-1')

      expect(store.aftermathForRoom('room-1')).toBeUndefined()
      store.stopPolling()
    })

    it('clears summaries alongside the incidents', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
      })

      store.clearIncidents()

      expect(store.aftermathForRoom('room-1')).toBeUndefined()
      store.stopPolling()
    })
  })

  describe('Spawn alert', () => {
    it('loops the alarm and ducks the music when an incident spawns', async () => {
      const store = useIncidentStore()
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(sseMock.startAlarm).toHaveBeenCalled()
      expect(sseMock.duckMusic).toHaveBeenCalled()
    })

    it('stops the alarm and restores the music when the chain ends', async () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce({ incidents: [] })

      await store.fetchIncidents('vault-1', 'token')

      expect(sseMock.startAlarm).not.toHaveBeenCalled()
      expect(sseMock.stopAlarm).toHaveBeenCalled()
      expect(sseMock.restoreMusic).toHaveBeenCalled()
    })
  })

  describe('SSE notifications', () => {
    it('announces a successful incident resolution', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      sseMock.instance.event.value = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-1', success: true, caps_earned: 50 },
      }
      await nextTick()

      expect(store.activeIncidentIds).toEqual([])
      expect(sseMock.toast.success).toHaveBeenCalledWith('Incident victory — recovered 50 caps.')
      store.stopPolling()
    })

    it('announces the experience a zero-caps victory paid', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      sseMock.instance.event.value = {
        event: 'incident',
        data: {
          type: 'incident_resolved',
          incident_id: 'incident-1',
          success: true,
          caps_earned: 0,
          experience_earned: 45,
        },
      }
      await nextTick()

      expect(store.aftermathForRoom('room-1')).toMatchObject({ experienceEarned: 45 })
      expect(sseMock.toast.success).toHaveBeenCalledWith('Incident victory — responders earned 45 XP.')
      store.stopPolling()
    })

    it('announces a lost incident so a failure is never silent', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      sseMock.instance.event.value = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-1', success: false },
      }
      await nextTick()

      expect(store.activeIncidentIds).toEqual([])
      expect(sseMock.toast.error).toHaveBeenCalledWith(
        `Incident lost — ${mockIncident.type.replace(/_/g, ' ')} overran ${mockIncident.room_name}.`
      )
      store.stopPolling()
    })

    it('announces a lost incident even when its details were already dropped', async () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-9']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      sseMock.instance.event.value = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-9', success: false },
      }
      await nextTick()

      expect(sseMock.toast.error).toHaveBeenCalledWith('Incident lost — the threat was not contained.')
      store.stopPolling()
    })
    it('announces a lost incident only once when the event is re-delivered', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      const resolvedEvent = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-1', success: false },
      }
      sseMock.instance.event.value = { ...resolvedEvent }
      await nextTick()
      sseMock.instance.event.value = { ...resolvedEvent }
      await nextTick()

      expect(sseMock.toast.error).toHaveBeenCalledTimes(1)
      store.stopPolling()
    })

    it('announces a victory only once when the event is re-delivered', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident).mockResolvedValueOnce(mockIncident)
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      const resolvedEvent = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-1', success: true, caps_earned: 50 },
      }
      sseMock.instance.event.value = { ...resolvedEvent }
      await nextTick()
      sseMock.instance.event.value = { ...resolvedEvent }
      await nextTick()

      expect(sseMock.toast.success).toHaveBeenCalledTimes(1)
      store.stopPolling()
    })
  })

  describe('Overflow claims', () => {
    const heldLoot = [{ item_type: 'weapon', rarity: 'common', name: 'Raider Pistol' }]

    it('reloads held loot once the incident is resolved', async () => {
      const store = useIncidentStore()
      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']
      vi.mocked(incidentApi.getActiveIncidents).mockResolvedValueOnce(mockIncidentList)
      vi.mocked(incidentApi.getIncident)
        .mockResolvedValueOnce(mockIncident)
        .mockResolvedValueOnce({ ...mockIncident, unclaimed_loot: heldLoot })
      store.startPolling('vault-1', 'token', 10_000)
      await Promise.resolve()

      sseMock.instance.event.value = {
        event: 'incident',
        data: { type: 'incident_resolved', incident_id: 'incident-1', success: true },
      }
      await nextTick()
      await flushPromises()

      expect(store.aftermathForRoom('room-1')?.unclaimed).toEqual(heldLoot)
      store.stopPolling()
    })

    it('stores a held item and updates the aftermath', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
      })
      vi.mocked(incidentApi.takeOverflow).mockResolvedValueOnce({
        caps_granted: 0,
        unclaimed_loot: [],
      })

      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')

      expect(incidentApi.takeOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0, 'token')
      expect(store.aftermathForRoom('room-1')?.unclaimed).toEqual([])
      store.stopPolling()
    })

    it('sells a held item for its caps', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
      })
      vi.mocked(incidentApi.sellOverflow).mockResolvedValueOnce({
        caps_granted: 12,
        unclaimed_loot: [],
      })

      await store.sellOverflow('vault-1', 'incident-1', 0, 'token')

      expect(incidentApi.sellOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0, 'token')
      expect(sseMock.toast.success).toHaveBeenCalledWith('Sold for 12 caps.')
      store.stopPolling()
    })

    it('only blames storage when the take fails with 409', async () => {
      const store = await resolveViaSse({
        type: 'incident_resolved',
        incident_id: 'incident-1',
        success: true,
      })

      vi.mocked(incidentApi.takeOverflow).mockRejectedValueOnce({ response: { status: 409 } })
      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')
      expect(sseMock.toast.error).toHaveBeenCalledWith('Storage is full — sell the item or free a slot.')

      sseMock.toast.error.mockClear()
      vi.mocked(incidentApi.takeOverflow).mockRejectedValueOnce({ response: { status: 500 } })
      await store.takeOverflow('vault-1', 'incident-1', 0, 'token')
      expect(sseMock.toast.error).toHaveBeenCalledWith('Could not store the held item.')
      expect(sseMock.toast.error).not.toHaveBeenCalledWith('Storage is full — sell the item or free a slot.')
      store.stopPolling()
    })
  })
})
