import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { incidentApi } from '../api/incident'
import type { Incident, IncidentListResponse } from '../models/incident'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useSse } from '@/core/composables/useEventStream'

export const useIncidentStore = defineStore('incident', () => {
  const incidents = ref<Map<string, Incident>>(new Map())
  const activeIncidentIds = ref<string[]>([])
  const isPolling = ref(false)
  const pollInterval = ref<number | null>(null)
  const sseConnected = ref(false)
  let sseInstance: ReturnType<typeof useSse> | null = null
  let fallbackTimer: ReturnType<typeof setTimeout> | null = null

  const { success: showSuccess, error: showError } = useToast()

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

      // Check for new incidents (spawn notifications)
      const spawned = newIds.filter((id) => !previousIds.includes(id))
      if (spawned.length > 0) {
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

  async function resolveIncident(
    vaultId: string,
    incidentId: string,
    token: string,
    success: boolean = true
  ): Promise<void> {
    try {
      const response = await incidentApi.resolveIncident(vaultId, incidentId, token, success)

      // Remove from active incidents
      activeIncidentIds.value = activeIncidentIds.value.filter((id) => id !== incidentId)
      incidents.value.delete(incidentId)

      // Show loot notification
      if (success && response.caps_earned > 0) {
        showSuccess(`Incident Resolved! Earned ${response.caps_earned} caps`)
      }

      return Promise.resolve()
    } catch (err) {
      handleStoreError(err, 'Failed to resolve incident')
      showError('Resolution Failed: Failed to resolve incident')
      throw err
    }
  }

  function startSseSubscription(vaultId: string, token: string): void {
    stopSseSubscription()

    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    sseInstance = useSse(`${apiBase}/api/v1/stream/incidents/${vaultId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    sseInstance.start()

    watch(
      () => sseInstance?.event.value,
      (evt) => {
        if (!evt || evt.event !== 'incident') return
        const data = evt.data as Record<string, unknown> | undefined
        if (!data || typeof data.type !== 'string') return

        switch (data.type) {
          case 'incident_spawned':
            sseConnected.value = true
            fetchIncidents(vaultId, token).catch(() => {})
            break

          case 'incident_resolved': {
            const resolvedId = data.incident_id as string | undefined
            if (resolvedId) {
              activeIncidentIds.value = activeIncidentIds.value.filter((id) => id !== resolvedId)
              incidents.value.delete(resolvedId)
            }
            break
          }

          case 'incident_spreading': {
            const spreadId = data.incident_id as string | undefined
            if (spreadId) {
              incidentApi.getIncident(vaultId, spreadId, token).then((incident) => {
                incidents.value.set(spreadId, incident)
              }).catch((err) => {
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
          if (pollInterval.value) {
            clearInterval(pollInterval.value)
            pollInterval.value = null
          }
        } else if (status === 'closed') {
          sseConnected.value = false
          if (fallbackTimer) {
            clearTimeout(fallbackTimer)
            fallbackTimer = null
          }
          fallbackTimer = setTimeout(() => {
            if (!sseConnected.value && !pollInterval.value) {
              pollInterval.value = window.setInterval(() => {
                fetchIncidents(vaultId, token).catch((err) => {
                  handleStoreError(err, 'Error polling incidents (SSE fallback)')
                })
              }, 10000)
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

    fetchIncidents(vaultId, token)
    if (token) {
      startSseSubscription(vaultId, token)
    }
    pollInterval.value = window.setInterval(() => {
      if (!sseConnected.value) {
        fetchIncidents(vaultId, token).catch((err) => {
          handleStoreError(err, 'Error polling incidents')
        })
      }
    }, intervalMs)
  }

  function stopPolling(): void {
    stopSseSubscription()
    if (pollInterval.value) {
      clearInterval(pollInterval.value)
      pollInterval.value = null
    }
    isPolling.value = false
  }

  function clearIncidents(): void {
    incidents.value.clear()
    activeIncidentIds.value = []
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
    isPolling,

    // Computed
    activeIncidents,
    hasActiveIncidents,
    incidentCountByVault,

    // Actions
    fetchIncidents,
    resolveIncident,
    startPolling,
    stopPolling,
    clearIncidents,
    getIncidentById,
    spawnDebugIncident,
  }
})
