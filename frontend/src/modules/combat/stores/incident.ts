import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { incidentApi } from '../api/incident'
import { IncidentStatus, getIncidentSound } from '../models/incident'
import type {
  Incident,
  IncidentAftermath,
  IncidentListResponse,
  IncidentLootItem,
  IncidentOutcome,
  IncidentTeamMember,
} from '../models/incident'
import { notifyErrorOnce, handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { audioManager } from '@/core/audio/audioManager'
import { useSse } from '@/core/composables/useEventStream'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { getDwellerDisplayName } from '@/modules/dwellers/models/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { usePolling } from '@/core/composables/usePolling'

export const useIncidentStore = defineStore('incident', () => {
  const incidents = ref<Map<string, Incident>>(new Map())
  const activeIncidentIds = ref<string[]>([])
  const aftermaths = ref<Map<string, IncidentAftermath>>(new Map())
  const incidentTeams = ref<Map<string, IncidentTeamMember[]>>(new Map())
  const isPolling = ref(false)
  const sseConnected = ref(false)
  let sseInstance: ReturnType<typeof useSse> | null = null
  let incidentPolling: ReturnType<typeof usePolling> | null = null
  let stopPollingCadenceWatch: (() => void) | null = null
  let pendingStartPolling: ReturnType<typeof usePolling> | null = null
  let pollingVaultId: string | null = null
  const announcedResolutions = new Set<string>()
  const announcedIncidentSounds = new Set<string>()
  const visibleSceneIds = new Set<string>()
  const pendingResolutionCues = new Map<string, Exclude<IncidentOutcome, 'unknown'>>()
  let resolutionQuietPending = false
  const seenEventMarkers = new Map<string, { count: number; lastId: string | undefined }>()
  let detailRequestOrder = 0
  let contextGeneration = 0
  const appliedDetailOrders = new Map<string, number>()
  const handledDispatchEvents = new Map<string, string>()

  const { success: showSuccess, error: showError, warning: showWarning } = useToast()

  // Computed
  const activeIncidents = computed(() => {
    return activeIncidentIds.value
      .map((id) => incidents.value.get(id))
      .filter((inc): inc is Incident => inc !== undefined)
  })

  const hasActiveIncidents = computed(() => activeIncidentIds.value.length > 0)

  watch(hasActiveIncidents, (active) => {
    if (active) {
      resolutionQuietPending = false
      audioManager.startAlarmLoop()
      audioManager.duckMusic()
    } else if (visibleSceneIds.size) {
      // Hold the shutdown until the open incident scene finishes its playback.
      resolutionQuietPending = true
    } else {
      audioManager.stopAlarmLoop()
      audioManager.restoreMusic()
    }
  })

  const incidentCountByVault = computed(() => {
    const counts: Record<string, number> = {}
    activeIncidents.value.forEach((inc) => {
      counts[inc.vault_id] = (counts[inc.vault_id] || 0) + 1
    })
    return counts
  })

  const aftermathForRoom = (roomId: string): IncidentAftermath | undefined =>
    aftermaths.value.get(roomId)

  const clearAftermath = (roomId: string): void => {
    aftermaths.value.delete(roomId)
  }

  const recordAftermath = (
    incident: Incident,
    outcome: IncidentOutcome,
    capsEarned: number,
    experienceEarned: number
  ): void => {
    aftermaths.value.set(incident.room_id, {
      incidentId: incident.id,
      roomId: incident.room_id,
      type: incident.type,
      roomName: incident.room_name,
      outcome,
      capsEarned,
      experienceEarned,
      loot: incident.loot,
      unclaimed: incident.unclaimed_loot ?? [],
      enemiesDefeated: incident.enemies_defeated,
      damageDealt: incident.damage_dealt,
      rounds: incident.events.length,
      scene: incident,
      sceneLoading: true,
    })
  }

  const findAftermath = (incidentId: string): IncidentAftermath | undefined =>
    [...aftermaths.value.values()].find((entry) => entry.incidentId === incidentId)

  const settleIncidentAudio = (): void => {
    if (!resolutionQuietPending || visibleSceneIds.size || hasActiveIncidents.value) return
    resolutionQuietPending = false
    audioManager.stopAlarmLoop()
    audioManager.restoreMusic()
  }

  // A visible scene owns the cue timing: play when its playback reaches the end.
  const queueResolutionSound = (
    incidentId: string | undefined,
    outcome: Exclude<IncidentOutcome, 'unknown'>
  ): void => {
    if (incidentId && visibleSceneIds.has(incidentId)) {
      pendingResolutionCues.set(incidentId, outcome)
      return
    }
    audioManager.play(outcome === 'victory' ? 'incidentVictory' : 'incidentDefeat', 'sfx')
  }

  const registerIncidentScene = (incidentId: string): void => {
    visibleSceneIds.add(incidentId)
  }

  const unregisterIncidentScene = (incidentId: string): void => {
    const wasVisible = visibleSceneIds.delete(incidentId)
    pendingResolutionCues.delete(incidentId)
    if (wasVisible) settleIncidentAudio()
  }

  const flushResolutionCue = (incidentId: string): void => {
    const outcome = pendingResolutionCues.get(incidentId)
    if (!outcome) {
      settleIncidentAudio()
      return
    }
    pendingResolutionCues.delete(incidentId)
    if (!hasActiveIncidents.value) audioManager.stopAlarmLoop()
    audioManager.play(outcome === 'victory' ? 'incidentVictory' : 'incidentDefeat', 'sfx')
    settleIncidentAudio()
  }

  const applyOverflow = (incidentId: string, unclaimed: IncidentLootItem[]): void => {
    const entry = findAftermath(incidentId)
    if (entry) entry.unclaimed = unclaimed
  }

  // The resolution frame carries no held loot, and the cached incident predates the
  // grant, so the aftermath reloads the resolved incident to learn what was held.
  const outcomeForStatus = (status: IncidentStatus): Exclude<IncidentOutcome, 'unknown'> | null => {
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
      // A closed vault/account can leave this request in flight.
      if (findAftermath(incidentId) !== entry) return
      entry.scene = incident
      entry.unclaimed = incident.unclaimed_loot ?? []
      entry.loot = incident.loot
      entry.enemiesDefeated = incident.enemies_defeated
      entry.damageDealt = incident.damage_dealt
      entry.rounds = incident.events.length
      entry.experienceEarned = incident.loot?.experience ?? entry.experienceEarned
      // A resolution frame that never arrived leaves the outcome unknown, but the record still knows it.
      const settled = outcomeForStatus(incident.status)
      if (entry.outcome === 'unknown' && settled) {
        entry.outcome = settled
        entry.capsEarned = incident.loot?.caps ?? 0
        queueResolutionSound(incidentId, settled)
      }
    } catch (error) {
      handleStoreError(error, 'Failed to load held incident loot')
    } finally {
      entry.sceneLoading = false
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
      handleStoreError(error, 'Failed to store held incident loot', false)
      const status = (error as { response?: { status?: number } } | null)?.response?.status
      notifyErrorOnce(
        error,
        status === 409
          ? 'Storage is full — sell the item or free a slot.'
          : 'Could not store the held item.'
      )
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
    }
  }

  // Actions
  async function fetchIncidents(
    vaultId: string,
    token: string,
    propagateError = false
  ): Promise<void> {
    const request = contextGeneration
    try {
      const response: IncidentListResponse = await incidentApi.getActiveIncidents(vaultId, token)
      if (request !== contextGeneration) return

      if (!response || !response.incidents || !Array.isArray(response.incidents)) {
        // An unconfirmed list is not a confirmed empty vault; fail closed.
        throw new Error('Malformed incident list response')
      }

      // Update active incidents list
      const newIds = response.incidents
        .map((inc) => inc.id)
        .filter((id) => !announcedResolutions.has(id))
      const previousIds = [...activeIncidentIds.value]

      // A resolution the SSE stream never delivered: the incident is simply gone
      // from the list. The list payload carries no outcome, so record what happened
      // without claiming a result we cannot know.
      previousIds
        .filter((id) => !newIds.includes(id))
        .forEach((id) => {
          const vanished = incidents.value.get(id)
          if (vanished) {
            recordAftermath(vanished, 'unknown', 0, 0)
            void refreshAftermathOverflow(vaultId, id, token)
          }
          incidentTeams.value.delete(id)
          appliedDetailOrders.delete(id)
          handledDispatchEvents.delete(id)
        })

      // Check for new incidents (spawn notifications)
      const spawned = newIds.filter((id) => !previousIds.includes(id))
      if (spawned.length > 0) {
        spawned.forEach((id) => {
          const incident = response.incidents.find((inc) => inc.id === id)
          if (incident) {
            showError(`Incident Alert! ${incident.type.replace('_', ' ').toUpperCase()} in vault!`)
            if (!announcedIncidentSounds.has(id)) {
              announcedIncidentSounds.add(id)
              audioManager.play(getIncidentSound(incident.type), 'sfx')
            }
          }
        })
      }

      // Fetch the designated responder team for newly spawned incidents and for
      // active incidents whose roster never loaded — a transient failure must
      // not leave the roster missing forever. A cached entry (even an empty
      // roster) is a successful load and is not refetched on every poll.
      const teamNeedsLoad = newIds.filter((id) => !incidentTeams.value.has(id))
      await Promise.all(teamNeedsLoad.map((id) => fetchIncidentTeam(vaultId, id, token)))
      if (request !== contextGeneration) return

      // Update store
      activeIncidentIds.value = newIds

      // Fetch full details for each incident; one failed detail must not discard the confirmed list.
      await Promise.all(
        newIds.map(async (id) => {
          try {
            const requestOrder = ++detailRequestOrder
            const incident = await incidentApi.getIncident(vaultId, id, token)
            if (request !== contextGeneration) return
            // Overlapping polls can resolve out of order; the newer request wins so
            // an older full window cannot replay the hit or lower the marker.
            if (requestOrder < (appliedDetailOrders.get(id) ?? 0)) return
            appliedDetailOrders.set(id, requestOrder)
            const previous = seenEventMarkers.get(id)
            const count = incident.events.length
            const lastEvent = incident.events.at(-1)
            const lastId = lastEvent?.id
            const lastIsCombat =
              lastEvent !== undefined && ['hit', 'round', 'containment'].includes(lastEvent.kind)
            // The journal only grows until it reaches the 40-line window, so a
            // shorter page is a stale snapshot and must not replace the store.
            if (previous && count < previous.count) return
            if (!previous) {
              seenEventMarkers.set(id, { count, lastId })
            } else if (lastId !== previous.lastId) {
              // The journal is a rolling window, so a saturated page still has to
              // sound when a combat line enters; an assignment or resolution must not.
              // Structured attacks sound at impact in the visible scene.
              if (lastIsCombat && !incident.events.some((event) => event.action))
                audioManager.play('incidentHit', 'sfx')
              seenEventMarkers.set(id, { count, lastId })
            }
            incidents.value.set(id, incident)
            // Hazard teams auto-deploy into the incident room; follow the moved
            // dwellers once per dispatch instead of relying on the spawn order.
            const dispatched = incident.events
              .slice()
              .reverse()
              .find((event) => event.kind === 'responders_dispatched')
            if (dispatched && handledDispatchEvents.get(id) !== dispatched.id) {
              handledDispatchEvents.set(id, dispatched.id)
              void fetchIncidentTeam(vaultId, id, token)
              void useDwellerFilterStore().fetchDwellersByVault(vaultId, token)
            }
          } catch (error) {
            handleStoreError(error, 'Failed to refresh incident details')
          }
        })
      )
    } catch (error) {
      // Fail closed: a transient failure must not make a live incident vanish.
      if (propagateError) throw error
      handleStoreError(error, 'Failed to fetch incidents')
    }
  }

  const getIncidentTeam = (incidentId: string): IncidentTeamMember[] =>
    incidentTeams.value.get(incidentId) ?? []

  const hasLoadedIncidentTeam = (incidentId: string): boolean => incidentTeams.value.has(incidentId)

  const totalResponderCount = computed(() =>
    activeIncidentIds.value.reduce(
      (total, id) => total + (incidentTeams.value.get(id)?.length ?? 0),
      0
    )
  )

  async function fetchIncidentTeam(
    vaultId: string,
    incidentId: string,
    token: string
  ): Promise<void> {
    const generation = contextGeneration
    try {
      const team = await incidentApi.getIncidentTeam(vaultId, incidentId, token)
      if (generation !== contextGeneration) return
      incidentTeams.value.set(incidentId, team)
    } catch (error) {
      handleStoreError(error, 'Failed to load incident team')
    }
  }

  async function assignResponders(
    vaultId: string,
    incidentId: string,
    dwellerIds: string[],
    token: string
  ): Promise<void> {
    const filterStore = useDwellerFilterStore()
    try {
      const result = await incidentApi.assignResponders(vaultId, incidentId, dwellerIds, token)
      await fetchIncidents(vaultId, token)
      await fetchIncidentTeam(vaultId, incidentId, token)
      await filterStore.fetchDwellersByVault(vaultId, token)
      const assignedIds = new Set(result.assigned_dweller_ids)
      const skippedIds = dwellerIds.filter((id) => !assignedIds.has(id))
      if (skippedIds.length) {
        const names = skippedIds.map((id) => {
          const dweller = filterStore.dwellers.find((entry) => entry.id === id)
          return dweller ? getDwellerDisplayName(dweller) : 'Unknown responder'
        })
        showWarning(
          `${assignedIds.size} of ${dwellerIds.length} responders assigned. Already defending: ${names.join(', ')}.`
        )
      } else {
        showSuccess('Responders assigned. They will fight on the next vault round.')
      }
    } catch (err) {
      handleStoreError(err, 'Failed to assign incident responders')
      throw err
    }
  }

  function watchPendingIncident(vaultId: string, incidentId: string, token: string): void {
    if (pollingVaultId !== vaultId) return
    pendingStartPolling?.stop()
    const expiresAt = Date.now() + 30000
    pendingStartPolling = usePolling(
      async () => {
        if (Date.now() >= expiresAt) {
          pendingStartPolling?.stop()
          return
        }
        await fetchIncidents(vaultId, token, true)
        if (activeIncidentIds.value.includes(incidentId)) pendingStartPolling?.stop()
      },
      { interval: 1000, immediate: false }
    )
    pendingStartPolling.resume()
  }

  function startIncidentPolling(vaultId: string, token: string, intervalMs: number): void {
    stopPollingCadenceWatch?.()
    const schedule = () => {
      incidentPolling?.stop()
      incidentPolling = usePolling(
        async () => {
          // SSE carries lifecycle changes, not rounds; active combat needs faster refreshes.
          if (!sseConnected.value || hasActiveIncidents.value) {
            await fetchIncidents(vaultId, token, true)
          }
        },
        {
          interval: hasActiveIncidents.value ? Math.min(intervalMs, 2000) : intervalMs,
          immediate: false,
        }
      )
      incidentPolling.resume()
    }
    stopPollingCadenceWatch = watch(hasActiveIncidents, schedule)
    schedule()
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
            if (data.is_paused === true) {
              void useVaultStore()
                .fetchGameState(vaultId, token)
                .catch((error) => {
                  handleStoreError(error, 'Failed to refresh automatic pause state')
                })
            }
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
              incidentTeams.value.delete(resolvedId)
              appliedDetailOrders.delete(resolvedId)
            }
            if (!isFirstNotice) break
            const capsEarned = typeof data.caps_earned === 'number' ? data.caps_earned : 0
            const experienceEarned =
              typeof data.experience_earned === 'number' ? data.experience_earned : 0
            if (resolved && resolvedId) {
              recordAftermath(
                resolved,
                data.success === true ? 'victory' : 'defeat',
                capsEarned,
                experienceEarned
              )
              void refreshAftermathOverflow(vaultId, resolvedId, token)
            }
            if (data.success === true) {
              queueResolutionSound(resolvedId, 'victory')
              showSuccess(
                capsEarned > 0
                  ? `Incident victory — recovered ${capsEarned} caps.`
                  : experienceEarned > 0
                    ? `Incident victory — responders earned ${experienceEarned} XP.`
                    : 'Incident resolved — responders earned experience.'
              )
            } else if (resolved) {
              queueResolutionSound(resolvedId, 'defeat')
              showError(
                `Incident lost — ${resolved.type.replace(/_/g, ' ')} overran ${resolved.room_name ?? 'the vault'}.`
              )
            } else {
              queueResolutionSound(resolvedId, 'defeat')
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
    contextGeneration += 1
    if (isPolling.value) {
      stopPolling()
    }

    isPolling.value = true
    pollingVaultId = vaultId

    void fetchIncidents(vaultId, token)
    if (token) {
      startSseSubscription(vaultId, token)
    }
    startIncidentPolling(vaultId, token, intervalMs)
  }

  function stopPolling(): void {
    contextGeneration += 1
    pendingStartPolling?.stop()
    pendingStartPolling = null
    pollingVaultId = null
    stopPollingCadenceWatch?.()
    stopPollingCadenceWatch = null
    stopSseSubscription()
    incidentPolling?.stop()
    incidentPolling = null
    isPolling.value = false
    // Clearing the active set unwinds the alarm and music through the watcher.
    activeIncidentIds.value = []
    visibleSceneIds.clear()
    pendingResolutionCues.clear()
    resolutionQuietPending = false
    audioManager.stopAlarmLoop()
    audioManager.restoreMusic()
    seenEventMarkers.clear()
    appliedDetailOrders.clear()
    handledDispatchEvents.clear()
  }

  function clearIncidents(): void {
    contextGeneration += 1
    incidents.value.clear()
    activeIncidentIds.value = []
    aftermaths.value.clear()
    incidentTeams.value.clear()
    announcedIncidentSounds.clear()
    seenEventMarkers.clear()
    appliedDetailOrders.clear()
    handledDispatchEvents.clear()
    visibleSceneIds.clear()
    pendingResolutionCues.clear()
    resolutionQuietPending = false
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

      throw err
    }
  }

  return {
    // State
    incidents,
    activeIncidentIds,
    aftermaths,
    incidentTeams,
    isPolling,

    // Computed
    activeIncidents,
    hasActiveIncidents,
    incidentCountByVault,
    totalResponderCount,

    // Actions
    fetchIncidents,
    watchPendingIncident,
    assignResponders,
    fetchIncidentTeam,
    getIncidentTeam,
    hasLoadedIncidentTeam,
    startPolling,
    stopPolling,
    clearIncidents,
    getIncidentById,
    registerScene: registerIncidentScene,
    unregisterScene: unregisterIncidentScene,
    flushResolutionCue,
    aftermathForRoom,
    clearAftermath,
    takeOverflow,
    sellOverflow,
    spawnDebugIncident,
  }
})
