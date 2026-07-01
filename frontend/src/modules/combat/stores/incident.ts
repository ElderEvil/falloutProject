import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref, computed, watch } from 'vue'
import { incidentApi } from '../api/incident'
import type { Incident, IncidentListResponse } from '../models/incident'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useSse } from '@/core/composables/useEventStream'
import { ApiError } from '@/core/plugins/httpClient'

export const useIncidentStore = defineStore('incident', () => {
  const incidents = ref<Map<string, Incident>>(new Map())
  const activeIncidentIds = ref<string[]>([])
  const isPolling = ref(false)
  const pollInterval = ref<number | null>(null)
  const sseConnected = ref(false)

  // Reactive refs for SSE lifecycle — drives watchers at store-init
  const activeVaultId = ref<string | null>(null)
  const authToken = ref<string>('')
  const sseInstance = ref<ReturnType<typeof useSse> | null>(null)
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

  // --- Top-level watchers (created ONCE at store-init) ---

  // Watch activeVaultId to drive SSE connect/disconnect
  watch(activeVaultId, (newId, oldId) => {
    if (oldId) {
      stopSseSubscription()
    }
    if (newId) {
      startSseSubscription(newId, authToken.value)
    }
  })

  // SSE event watcher — reactively follows sseInstance
  watch(
    () => sseInstance.value?.event?.value,
    (evt) => {
      const vaultId = activeVaultId.value
      if (!evt || evt.event !== 'incident' || !vaultId) return
      const data = evt.data as Record<string, unknown> | undefined
      if (!data || typeof data.type !== 'string') return

      switch (data.type) {
        case 'incident_spawned':
          sseConnected.value = true
          fetchIncidents(vaultId).catch(() => {})
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
            incidentApi
              .getIncident(vaultId, spreadId)
              .then((incident) => {
                incidents.value.set(spreadId, incident)
              })
              .catch(() => {})
          }
          break
        }
      }
    }
  )

  // SSE status watcher — handles open/closed for fallback polling
  watch(
    () => sseInstance.value?.status?.value,
    (status) => {
      const vaultId = activeVaultId.value
      if (!vaultId) return

      if (status === 'open') {
        sseConnected.value = true
        if (pollInterval.value) {
          clearInterval(pollInterval.value)
          pollInterval.value = null
        }
      } else if (status === 'closed') {
        sseConnected.value = false
        fallbackTimer = setTimeout(() => {
          if (!sseConnected.value && !pollInterval.value) {
            pollInterval.value = window.setInterval(() => {
              fetchIncidents(vaultId).catch((err) => {
                handleStoreError(err, 'Error polling incidents (SSE fallback)')
              })
            }, 10000)
          }
        }, 30000)
      }
    }
  )

  // Actions
  async function fetchIncidents(vaultId: string, _token?: string): Promise<void> {
    try {
      const response: IncidentListResponse = await incidentApi.getActiveIncidents(vaultId)

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
          const incident = await incidentApi.getIncident(vaultId, id)
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
    _token?: string,
    success: boolean = true
  ): Promise<void> {
    try {
      const response = await incidentApi.resolveIncident(vaultId, incidentId, success)

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
    const sse = useSse(`${apiBase}/api/v1/stream/incidents/${vaultId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    sseInstance.value = sse
    sse.start()
  }

  function stopSseSubscription(): void {
    if (sseInstance.value) {
      sseInstance.value.stopReconnect()
      sseInstance.value.close()
      sseInstance.value = null
    }
    sseConnected.value = false
    if (fallbackTimer) {
      clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
  }

  function startPolling(vaultId: string, token?: string, intervalMs: number = 10000): void {
    if (isPolling.value) {
      stopPolling()
    }

    isPolling.value = true
    authToken.value = token ?? ''

    fetchIncidents(vaultId)
    activeVaultId.value = vaultId
    pollInterval.value = window.setInterval(() => {
      if (!sseConnected.value) {
        fetchIncidents(vaultId).catch((err) => {
          handleStoreError(err, 'Error polling incidents')
        })
      }
    }, intervalMs)
  }

  function stopPolling(): void {
    stopSseSubscription()
    activeVaultId.value = null
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
    _token?: string,
    incidentType?: string
  ): Promise<void> {
    try {
      const result = await incidentApi.spawnIncident(vaultId, incidentType)

      // Show success notification
      showSuccess(
        `Incident Spawned: ${result.type.replace(/_/g, ' ')} (Difficulty: ${result.difficulty})`
      )

      // Immediately fetch updated incidents
      await fetchIncidents(vaultId)
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to spawn incident')

      let errorMessage = 'Failed to spawn incident'
      if (err instanceof ApiError) {
        errorMessage = typeof err.detail === 'string' ? err.detail : errorMessage
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

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useIncidentStore, import.meta.hot))
}
