import { defineStore } from 'pinia'
import { ref } from 'vue'
import { expeditionSiteApi } from '../api/expeditionSite'
import type { AvailableSiteView, SiteAvailabilityView, SiteRoomView } from '../api/expeditionSite'
import { handleStoreError } from '@/core/utils/errorHandler'

export type SiteRunStatus = 'in_room' | 'retreated' | 'cleared' | 'died'

export const SITE_TERMINAL_STATUSES: SiteRunStatus[] = ['retreated', 'cleared', 'died']

export function isTerminal(status: string): boolean {
  return SITE_TERMINAL_STATUSES.includes(status as SiteRunStatus)
}

export const useExpeditionSiteStore = defineStore('expeditionSite', () => {
  const availableSites = ref<AvailableSiteView[]>([])
  const availability = ref<SiteAvailabilityView | null>(null)
  const room = ref<SiteRoomView | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentExplorationId = ref<string | null>(null)
  let scopeVersion = 0
  let availabilityRequest = 0

  // Gap 4.3: room state is scoped to the exploration that loaded it. Acting on
  // a different exploration must never render a stale room from a previous one.
  function scopeToExploration(explorationId: string): void {
    if (explorationId !== currentExplorationId.value) {
      scopeVersion++
      availabilityRequest++
      room.value = null
      availableSites.value = []
      availability.value = null
      error.value = null
      currentExplorationId.value = explorationId
    }
  }

  async function runRequest<T>(
    explorationId: string,
    request: () => Promise<T>,
    failureMessage: string,
    apply: (value: T) => void
  ): Promise<T> {
    scopeToExploration(explorationId)
    const version = scopeVersion
    isLoading.value = true
    error.value = null
    try {
      const value = await request()
      if (version === scopeVersion) apply(value)
      return value
    } catch (err) {
      if (version === scopeVersion) {
        handleStoreError(err, failureMessage)
        error.value = failureMessage
      }
      throw err
    } finally {
      if (version === scopeVersion) isLoading.value = false
    }
  }

  function fetchAvailability(explorationId: string): Promise<SiteAvailabilityView> {
    scopeToExploration(explorationId)
    const requestId = ++availabilityRequest
    return runRequest(
      explorationId,
      () => expeditionSiteApi.getAvailability(explorationId),
      'Failed to load available expedition sites',
      (nextAvailability) => {
        if (requestId !== availabilityRequest) return
        availability.value = nextAvailability
        availableSites.value = nextAvailability.sites
      }
    )
  }

  async function enterSite(explorationId: string, siteId: string): Promise<SiteRoomView> {
    return runRequest(
      explorationId,
      () => expeditionSiteApi.enterSite(explorationId, siteId),
      'Failed to enter expedition site',
      (nextRoom) => {
        room.value = nextRoom
      }
    )
  }

  async function resolveNode(explorationId: string, choiceId?: string): Promise<SiteRoomView> {
    return runRequest(
      explorationId,
      () => expeditionSiteApi.resolveNode(explorationId, choiceId),
      'Failed to resolve expedition node',
      (nextRoom) => {
        room.value = nextRoom
      }
    )
  }

  async function retreat(explorationId: string): Promise<SiteRoomView> {
    return runRequest(
      explorationId,
      () => expeditionSiteApi.retreatSite(explorationId),
      'Failed to retreat from expedition site',
      (nextRoom) => {
        room.value = nextRoom
      }
    )
  }

  async function fetchCurrentRoom(explorationId: string): Promise<SiteRoomView | null> {
    return runRequest(
      explorationId,
      () => expeditionSiteApi.getCurrentRoom(explorationId),
      'Failed to load current expedition room',
      (currentRoom) => {
        room.value = currentRoom
      }
    )
  }

  function reset(): void {
    scopeVersion++
    availabilityRequest++
    room.value = null
    availableSites.value = []
    availability.value = null
    error.value = null
    currentExplorationId.value = null
    isLoading.value = false
  }

  return {
    availableSites,
    availability,
    room,
    isLoading,
    error,
    currentExplorationId,
    fetchAvailability,
    enterSite,
    resolveNode,
    retreat,
    fetchCurrentRoom,
    reset,
  }
})
