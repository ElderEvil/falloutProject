import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { incidentApi } from '../api/incident'
import { IncidentStatus } from '../models/incident'
import type {
  Incident,
  IncidentAftermath,
  IncidentListResponse,
  IncidentLootItem,
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
      unclaimed: incident.unclaimed_loot ?? [],
      enemiesDefeated: incident.enemies_defeated,
      damageDealt: incident.damage_dealt,
      rounds: incident.events.length,
    })
  }

  const findAftermath = (incidentId: string): IncidentAftermath | undefined =>
    [...aftermaths.value.values()].find((entry) => entry.incidentId === incidentId)

  const applyOverflow = (incidentId: string, unclaimed: IncidentLootItem[]): void => {
    const entry = findAftermath(incidentId)
    if (entry) entry.unclaimed = unclaimed
  }

  // The resolution frame carries no held loot, and the cached incident predates the
  // grant, so the aftermath reloads the resolved incident to learn what was held.
  const outcomeForStatus = (status: IncidentStatus): IncidentOutcome | null => {
    if (status === IncidentStatus.RESOLVED) return 'victory'
    if (status === IncidentStatus.FAILED) return 'defeat'
    return null
  }

  const refreshAftermathOverflow = async (
    vaultId: string,
    incidentId: string,
    token: string
  ): Promise<void> => {
    const entry = findAftermath(incidentId)
    if (!entry) return
    try {
      const incident = await incidentApi.getIncident(vaultId, incidentId, token)
      entry.unclaimed = incident.unclaimed_loot ?? []
      entry.loot = incident.loot
      entry.enemiesDefeated = incident.enemies_defeated
      entry.damageDealt = incident.damage_dealt
      entry.rounds = incident.events.length
      // A resolution frame that never arrived leaves the outcome unknown, but the record still knows it.
      const settled = outcomeForStatus(incident.status)
      if (entry.outcome === 'unknown' && settled) {
        entry.outcome = settled
        entry.capsEarned = incident.loot?.caps ?? 0
      }
    } catch (error) {
      handleStoreError(error, 'Failed to load held incident loot')
    }
  }

  async function takeOverflow(
    vaultId: string,
    incidentId: string,
    index: number,
    token: string
  ): Promise<void> {
    try {
      const response = await incidentApi.takeOverflow(vaultId, incidentId, index, token)
      applyOverflow(incidentId, response.unclaimed_loot)
      showSuccess('Held loot stored.')
    } catch (error) {
      handleStoreError(error, 'Failed to store held incident loot')
      const status = (error as { response?: { status?: number } } | null)?.response?.status
      showError(status === 409 ? 'Storage is full — sell the item or free a slot.' : 'Could not store the held item.')
    }
  }

  async function sellOverflow(
    vaultId: string,
    incidentId: string,
    index: number,
    token: string
  ): Promise<void> {
    try {
      const response = await incidentApi.sellOverflow(vaultId, incidentId, index, token)
      applyOverflow(incidentId, response.unclaimed_loot)
      showSuccess(`Sold for ${response.caps_granted} caps.`)
    } catch (error) {
      handleStoreError(error, 'Failed to sell held incident loot')
      showError('Could not sell the held item.')
    }
  }

  // Actions
  async function fetchIncidents(vaultId: string, token: string): Promise<void> {
    try {
      const response: IncidentListResponse = await incidentApi.getActiveIncidents(vaultId, token)

      if (!response || !response.incidents || !Array.isArray(response.incidents)) {
        // An unconfirmed list is not a confirmed empty vault; fail closed.
        handleStoreError(new Error('Malformed incident list response'), 'Failed to fetch incidents')
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
          if (vanished) {
            recordAftermath(vanished, 'unknown', 0)
            void refreshAftermathOverflow(vaultId, id, token)
          }
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

      // Fetch full details for each incident; one failed detail must not discard the confirmed list.
      await Promise.all(
        newIds.map(async (id) => {
          try {
            const incident = await incidentApi.getIncident(vaultId, id, token)
            incidents.value.set(id, incident)
          } catch (error) {
            handleStoreError(error, 'Failed to refresh incident details')
          }
        })
      )
    } catch (error) {
      // Fail closed: a transient failure must not make a live incident vanish.
      handleStoreError(error, 'Failed to fetch incidents')
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
        // The stream carries spawn, spread and resolution only — never a round — so
        // an active overlay still needs this refresh to advance its battle log.
        if (!sseConnected.value || activeIncidentIds.value.length > 0) {
          await fetchIncidents(vaultId, token)
        }
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
            if (resolved && resolvedId) {
              recordAftermath(
                resolved,
                data.success === true ? 'victory' : 'defeat',
                typeof data.caps_earned === 'number' ? data.caps_earned : 0
              )
              void refreshAftermathOverflow(vaultId, resolvedId, token)
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

    // The stream carries spawn, spread and resolution — never a round — so the
    // interval keeps ticking for as long as the vault is polled and the refresh
    // itself decides whether a fetch is needed. Pausing it here would freeze any
    // open overlay on its first fetch.
    watch(
      () => sseInstance?.status.value,
      (status) => {
        sseConnected.value = status === 'open'
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
    takeOverflow,
    sellOverflow,
    spawnDebugIncident,
  }
})
