import { defineStore } from 'pinia'
import { ref } from 'vue'
import { expeditionSiteApi } from '../api/expeditionSite'
import type { AvailableSiteView, SiteRoomView } from '../api/expeditionSite'
import { handleStoreError } from '@/core/utils/errorHandler'

export type SiteRunStatus = 'entered' | 'in_room' | 'retreated' | 'cleared' | 'died'

export const SITE_TERMINAL_STATUSES: SiteRunStatus[] = ['retreated', 'cleared', 'died']

export function isTerminal(status: string): boolean {
  return SITE_TERMINAL_STATUSES.includes(status as SiteRunStatus)
}

export const useExpeditionSiteStore = defineStore('expeditionSite', () => {
  const availableSites = ref<AvailableSiteView[]>([])
  const room = ref<SiteRoomView | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentExplorationId = ref<string | null>(null)

  // Gap 4.3: room state is scoped to the exploration that loaded it. Acting on
  // a different exploration must never render a stale room from a previous one.
  function scopeToExploration(explorationId: string): void {
    if (explorationId !== currentExplorationId.value) {
      room.value = null
      error.value = null
      currentExplorationId.value = explorationId
    }
  }

  async function fetchAvailableSites(explorationId: string): Promise<AvailableSiteView[]> {
    isLoading.value = true
    error.value = null
    try {
      const sites = await expeditionSiteApi.listAvailableSites(explorationId)
      availableSites.value = sites
      return sites
    } catch (err) {
      handleStoreError(err, 'Failed to load available expedition sites')
      error.value = 'Failed to load available expedition sites'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function enterSite(explorationId: string, siteId: string): Promise<SiteRoomView> {
    scopeToExploration(explorationId)
    isLoading.value = true
    error.value = null
    try {
      const nextRoom = await expeditionSiteApi.enterSite(explorationId, siteId)
      room.value = nextRoom
      return nextRoom
    } catch (err) {
      handleStoreError(err, 'Failed to enter expedition site')
      error.value = 'Failed to enter expedition site'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function resolveNode(explorationId: string, choiceId?: string): Promise<SiteRoomView> {
    scopeToExploration(explorationId)
    isLoading.value = true
    error.value = null
    try {
      const nextRoom = await expeditionSiteApi.resolveNode(explorationId, choiceId)
      room.value = nextRoom
      return nextRoom
    } catch (err) {
      handleStoreError(err, 'Failed to resolve expedition node')
      error.value = 'Failed to resolve expedition node'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function retreat(explorationId: string): Promise<SiteRoomView> {
    scopeToExploration(explorationId)
    isLoading.value = true
    error.value = null
    try {
      const nextRoom = await expeditionSiteApi.retreatSite(explorationId)
      room.value = nextRoom
      return nextRoom
    } catch (err) {
      handleStoreError(err, 'Failed to retreat from expedition site')
      error.value = 'Failed to retreat from expedition site'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchCurrentRoom(explorationId: string): Promise<SiteRoomView | null> {
    scopeToExploration(explorationId)
    isLoading.value = true
    error.value = null
    try {
      const currentRoom = await expeditionSiteApi.getCurrentRoom(explorationId)
      room.value = currentRoom
      return currentRoom
    } catch (err) {
      handleStoreError(err, 'Failed to load current expedition room')
      error.value = 'Failed to load current expedition room'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function clearError(): void {
    error.value = null
  }

  function reset(): void {
    room.value = null
    availableSites.value = []
    error.value = null
    currentExplorationId.value = null
  }

  return {
    availableSites,
    room,
    isLoading,
    error,
    currentExplorationId,
    fetchAvailableSites,
    enterSite,
    resolveNode,
    retreat,
    fetchCurrentRoom,
    clearError,
    reset,
  }
})
