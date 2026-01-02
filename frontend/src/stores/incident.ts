import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { incidentApi } from '@/api/incident'
import type { Incident, IncidentListResponse } from '@/models/incident'
import { useNotificationStore } from './notification'

export const useIncidentStore = defineStore('incident', () => {
  const incidents = ref<Map<string, Incident>>(new Map())
  const activeIncidentIds = ref<string[]>([])
  const isPolling = ref(false)
  const pollInterval = ref<number | null>(null)

  const notificationStore = useNotificationStore()

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

      console.log('[IncidentStore] fetchIncidents response:', response)

      // Safety check
      if (!response || !response.incidents || !Array.isArray(response.incidents)) {
        console.warn('Invalid response from getActiveIncidents:', response)
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
            notificationStore.error(
              'Incident Alert!',
              `${incident.type.replace('_', ' ').toUpperCase()} in vault!`
            )
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
      console.error('Failed to fetch incidents:', error)
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
        notificationStore.success(
          'Incident Resolved!',
          `Earned ${response.caps_earned} caps`
        )
      }

      return Promise.resolve()
    } catch (error) {
      console.error('Failed to resolve incident:', error)
      notificationStore.error(
        'Resolution Failed',
        'Failed to resolve incident'
      )
      throw error
    }
  }

  function startPolling(vaultId: string, token: string, intervalMs: number = 10000): void {
    if (isPolling.value) {
      stopPolling()
    }

    isPolling.value = true

    // Initial fetch
    fetchIncidents(vaultId, token)

    // Set up polling
    pollInterval.value = window.setInterval(() => {
      fetchIncidents(vaultId, token).catch((err) => {
        console.error('Error polling incidents:', err)
      })
    }, intervalMs)
  }

  function stopPolling(): void {
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

  async function spawnDebugIncident(vaultId: string, token: string, incidentType?: string): Promise<void> {
    try {
      const result = await incidentApi.spawnIncident(vaultId, token, incidentType)

      // Show success notification
      notificationStore.success(
        'Incident Spawned',
        `${result.type.replace(/_/g, ' ')} spawned (Difficulty: ${result.difficulty})`
      )

      // Immediately fetch updated incidents
      await fetchIncidents(vaultId, token)
    } catch (error: unknown) {
      console.error('Failed to spawn incident:', error)

      let errorMessage = 'Failed to spawn incident'
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { detail?: string } } }
        errorMessage = axiosError.response?.data?.detail || errorMessage
      }

      notificationStore.error('Spawn Failed', errorMessage)
      throw error
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
