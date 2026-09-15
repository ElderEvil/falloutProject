import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { incidentApi } from '../api/incident'
import type {
  Incident,
  IncidentAftermath,
  IncidentListResponse,
  IncidentOutcome,
} from '../models/incident'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useSound } from '@/core/composables/useSound'
import { useSse } from '@/core/composables/useEventStream'
import { usePolling } from '@/core/composables/usePolling'

export const useIncidentStore = defineStore('incident', () => {
  const incidents = ref<Map<string, Incident>>(new Map())
  const activeIncidentIds = ref<string[]>([])
  const aftermaths = ref<Map<string, IncidentAftermath>>(new Map())
  const isPolling = ref(false)
  const sseConnected = ref(false)
  let sseInstance: ReturnType<typeof useSse> | null = null
  let fallbackTimer: ReturnType<typeof setTimeout> | null = null
  let incidentPolling: ReturnType<typeof usePolling> | null = null
  const announcedResolutions = new Set<string>()

  const { success: showSuccess, error: showError } = useToast()
  const { playSound } = useSound()

  // Computed
  const activeIncidents = computed(() => {
    return activeIncidentIds.value
      .map((id) => incidents.value.get(id))
      .filter((inc): inc is Incident => inc !== undefined)
  })

  const hasActiveIncidents = computed(() => activeIncidentIds.value.length > 0)

  const incidentCountByVault = computed(() => {
    const counts: Record<string, number> = {}
    activeIncidents.value.forEach((inc) => {
      counts[inc.vault_id] = (counts[inc.vault_id] || 0) + 1
    })
    return counts
  })

  const aftermathForRoom = (roomId: string): IncidentAftermath | undefined => aftermaths.value.get(roomId)

  const clearAftermath = (roomId: string): void => {
    aftermaths.value.delete(roomId)
  }

  const recordAftermath = (incident: Incident, outcome: IncidentOutcome, capsEarned: number): void => {
    aftermaths.value.set(incident.room_id, {
      incidentId: incident.id,
      roomId: incident.room_id,
      type: incident.type,
      roomName: incident.room_name,
      outcome,
      capsEarned,
      loot: incident.loot,
      enemiesDefeated: incident.enemies_defeated,
      damageDealt: incident.damage_dealt,
      rounds: incident.events.length,
    })
  }

  // Actions
  async function fetchIncidents(vaultId: string, token: string): Promise<void> {
    try {
      const response: IncidentListResponse = await incidentApi.getActiveIncidents(vaultId, token)

      // Safety check
      if (!response || !response.incidents || !Array.isArray(response.incidents)) {
        activeIncidentIds.value = []
        return
      }

      // Update active incidents list
      const newIds = response.incidents.map((inc) => inc.id)
      const previousIds = [...activeIncidentIds.value]

      // A resolution the SSE stream never delivered: the incident is simply gone
      // from the list. The list payload carries no outcome, so record what happened
      // without claiming a result we cannot know.
      previousIds
        .filter((id) => !newIds.includes(id))
        .forEach((id) => {
          const vanished = incidents.value.get(id)
          if (vanished) recordAftermath(vanished, 'unknown', 0)
        })

      // Check for new incidents (spawn notifications)
      const spawned = newIds.filter((id) => !previousIds.includes(id))
      if (spawned.length > 0) {
        playSound('notification')
        spawned.forEach((id) => {
          const incident = response.incidents.find((inc) => inc.id === id)
          if (incident) {
            showError(`Incident Alert! ${incident.type.replace('_', ' ').toUpperCase()} in vault!`)
          }
        })
      }

      // Update store
      activeIncidentIds.value = newIds

      // Fetch full details for each incident
      await Promise.all(
        newIds.map(async (id) => {
          const incident = await incidentApi.getIncident(vaultId, id, token)
          incidents.value.set(id, incident)
        })
      )
    } catch (error) {
      handleStoreError(error, 'Failed to fetch incidents')
      // Don't throw - just set empty state so the app continues working
      activeIncidentIds.value = []
    }
  }

  async function assignResponders(
    vaultId: string,
    incidentId: string,
    dwellerIds: string[],
    token: string
  ): Promise<void> {
    try {
      await incidentApi.assignResponders(vaultId, incidentId, dwellerIds, token)
      await fetchIncidents(vaultId, token)
      showSuccess('Responders assigned. They will fight on the next vault round.')
    } catch (err) {
      handleStoreError(err, 'Failed to assign incident responders')
      showError('Responder assignment failed')
      throw err
    }
  }

  function startIncidentPolling(vaultId: string, token: string, intervalMs: number): void {
    incidentPolling?.pause()
    incidentPolling = usePolling(
      async () => {
        if (!sseConnected.value) await fetchIncidents(vaultId, token)
      },
      { interval: intervalMs, immediate: false }
    )
    incidentPolling.resume()
  }

  function startSseSubscription(vaultId: string, token: string): void {
    stopSseSubscription()

    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    sseInstance = useSse(`${apiBase}/api/v1/stream/incidents/${vaultId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    void sseInstance.start()

    watch(
      () => sseInstance?.event.value,
      (evt) => {
        if (!evt || evt.event !== 'incident') return
        const data = evt.data as Record<string, unknown> | undefined
        if (!data || typeof data.type !== 'string') return

        switch (data.type) {
          case 'incident_spawned':
            sseConnected.value = true
            void fetchIncidents(vaultId, token)
            break

          case 'incident_resolved': {
            const resolvedId = data.incident_id as string | undefined
            const resolved = resolvedId ? incidents.value.get(resolvedId) : undefined
            const isFirstNotice = resolvedId === undefined || !announcedResolutions.has(resolvedId)
            if (resolvedId) {
              announcedResolutions.add(resolvedId)
              activeIncidentIds.value = activeIncidentIds.value.filter((id) => id !== resolvedId)
              incidents.value.delete(resolvedId)
            }
            if (!isFirstNotice) break
            if (resolved) {
              recordAftermath(
                resolved,
                data.success === true ? 'victory' : 'defeat',
                typeof data.caps_earned === 'number' ? data.caps_earned : 0
              )
            }
            if (data.success === true) {
              const capsEarned = typeof data.caps_earned === 'number' ? data.caps_earned : 0
              showSuccess(
                capsEarned > 0
                  ? `Incident victory — recovered ${capsEarned} caps.`
                  : 'Incident resolved — responders earned experience.'
              )
            } else if (resolved) {
              showError(
                `Incident lost — ${resolved.type.replace(/_/g, ' ')} overran ${resolved.room_name ?? 'the vault'}.`
              )
            } else {
              showError('Incident lost — the threat was not contained.')
            }
            break
          }

          case 'incident_spreading': {
            const spreadId = data.incident_id as string | undefined
            if (spreadId) {
              incidentApi
                .getIncident(vaultId, spreadId, token)
                .then((incident) => {
                  incidents.value.set(spreadId, incident)
                })
                .catch((err) => {
                  handleStoreError(err, 'Failed to fetch spread incident details')
                })
            }
            break
          }
        }
      }
    )

    watch(
      () => sseInstance?.status.value,
      (status) => {
        if (status === 'open') {
          sseConnected.value = true
          incidentPolling?.pause()
        } else if (status === 'closed') {
          sseConnected.value = false
          if (fallbackTimer) {
            clearTimeout(fallbackTimer)
            fallbackTimer = null
          }
          fallbackTimer = setTimeout(() => {
            if (!sseConnected.value && isPolling.value) {
              startIncidentPolling(vaultId, token, 10000)
            }
          }, 30000)
        }
      }
    )
  }

  function stopSseSubscription(): void {
    if (sseInstance) {
      sseInstance.stopReconnect()
      sseInstance.close()
      sseInstance = null
    }
    sseConnected.value = false
    if (fallbackTimer) {
      clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
  }

  function startPolling(vaultId: string, token: string, intervalMs: number = 10000): void {
    if (isPolling.value) {
      stopPolling()
    }

    isPolling.value = true

    void fetchIncidents(vaultId, token)
    if (token) {
      startSseSubscription(vaultId, token)
    }
    startIncidentPolling(vaultId, token, intervalMs)
  }

  function stopPolling(): void {
    stopSseSubscription()
    incidentPolling?.pause()
    incidentPolling = null
    isPolling.value = false
  }

  function clearIncidents(): void {
    incidents.value.clear()
    activeIncidentIds.value = []
    aftermaths.value.clear()
  }

  function getIncidentById(id: string): Incident | undefined {
    return incidents.value.get(id)
  }

  async function spawnDebugIncident(
    vaultId: string,
    token: string,
    incidentType?: string
  ): Promise<void> {
    try {
      const result = await incidentApi.spawnIncident(vaultId, token, incidentType)

      // Show success notification
      showSuccess(
        `Incident Spawned: ${result.type.replace(/_/g, ' ')} (Difficulty: ${result.difficulty})`
      )

      // Immediately fetch updated incidents
      await fetchIncidents(vaultId, token)
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to spawn incident')

      let errorMessage = 'Failed to spawn incident'
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } }
        errorMessage = axiosError.response?.data?.detail || errorMessage
      }

      showError(`Spawn Failed: ${errorMessage}`)
      throw err
    }
  }

  return {
    // State
    incidents,
    activeIncidentIds,
    aftermaths,
    isPolling,

    // Computed
    activeIncidents,
    hasActiveIncidents,
    incidentCountByVault,

    // Actions
    fetchIncidents,
    assignResponders,
    startPolling,
    stopPolling,
    clearIncidents,
    getIncidentById,
    aftermathForRoom,
    clearAftermath,
    spawnDebugIncident,
  }
})
