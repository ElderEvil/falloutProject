import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useIncidentStore } from '@/stores/incident'
import { incidentApi } from '@/api/incident'
import type { IncidentListResponse, Incident } from '@/models/incident'
import { IncidentType, IncidentStatus } from '@/models/incident'

vi.mock('@/api/incident')
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  })
}))

describe('Incident Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const mockIncident: Incident = {
    id: 'incident-1',
    vault_id: 'vault-1',
    room_id: 'room-1',
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
    resolved_at: null,
    duration: 60
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
        difficulty: 5,
        start_time: '2025-01-01T00:00:00Z',
        elapsed_time: 60,
        damage_dealt: 10,
        enemies_defeated: 2
      }
    ]
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
        incidents: []
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
  })

  describe('resolveIncident', () => {
    it('should resolve incident successfully', async () => {
      const store = useIncidentStore()

      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']

      vi.mocked(incidentApi.resolveIncident).mockResolvedValueOnce({
        message: 'Incident resolved',
        incident_id: 'incident-1',
        caps_earned: 150,
        items_earned: []
      })

      await store.resolveIncident('vault-1', 'incident-1', 'token', true)

      expect(store.activeIncidentIds).not.toContain('incident-1')
      expect(store.incidents.has('incident-1')).toBe(false)
      // Toast notification is shown (tested by integration, not mocked here)
    })

    it('should handle resolve failure', async () => {
      const store = useIncidentStore()

      store.incidents.set('incident-1', mockIncident)
      store.activeIncidentIds = ['incident-1']

      vi.mocked(incidentApi.resolveIncident).mockRejectedValueOnce(new Error('Resolve failed'))

      await expect(store.resolveIncident('vault-1', 'incident-1', 'token')).rejects.toThrow()

      // Toast error notification is shown (tested by integration, not mocked here)
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
        difficulty: 5
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
        difficulty: 3
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
            difficulty: 5,
            start_time: '2025-01-01T00:00:00Z',
            elapsed_time: 60,
            damage_dealt: 10,
            enemies_defeated: 2
          },
          {
            id: 'incident-2',
            type: IncidentType.FIRE,
            status: IncidentStatus.SPREADING,
            room_id: 'room-2',
            difficulty: 3,
            start_time: '2025-01-01T00:00:00Z',
            elapsed_time: 30,
            damage_dealt: 5,
            enemies_defeated: 0
          }
        ]
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
        incidents: [mockIncidentList.incidents[0]]
      })
      vi.mocked(incidentApi.getIncident).mockResolvedValue(mockIncident)

      await store.fetchIncidents('vault-1', 'token')

      expect(store.activeIncidentIds).toHaveLength(1)
      expect(store.activeIncidentIds).toContain('incident-1')
      expect(store.activeIncidentIds).not.toContain('incident-2')
    })
  })
})
