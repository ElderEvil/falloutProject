import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useSse } from '@/core/composables/useEventStream'
import { addPendingReport } from '../composables/usePendingReports'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { explorationUpdatesDisabled } from '@/modules/profile/stores/profile'
import {
  explorationApi,
  type ExplorationCompleteResponse,
  type ExplorationPartyMember,
  type ExplorationSendRequest,
} from '../api/exploration'
import type { ExplorationEventType } from '@/modules/exploration/models/exploration'

export interface ExplorationEvent {
  type: ExplorationEventType
  description: string
  timestamp: string
  time_elapsed_hours: number
  event?: string
  site_id?: string
  location_name?: string
  location_id?: string
  coord_x?: number
  coord_y?: number
  health_loss?: number
  health_restored?: number
  radiation_gain?: number
  radiation_removed?: number
  loot?: {
    item: {
      name: string
      rarity: string
      value: number
    }
    item_type?: string
    caps: number
  }
}

export interface LootItem {
  item_name: string
  quantity: number
  rarity: string
  item_type?: string // 'junk', 'weapon', or 'outfit'
  found_at: string
}

export interface Exploration {
  id: string
  vault_id: string
  dweller_id: string
  target_location_id?: string | null
  status: 'active' | 'returning' | 'completed' | 'recalled'
  duration: number
  start_time: string
  paused_at?: string | null
  end_time: string | null
  return_started_at?: string | null
  return_completes_at?: string | null
  recalled_early?: boolean
  events: ExplorationEvent[]
  loot_collected: LootItem[]
  total_distance: number
  total_caps_found: number
  enemies_encountered: number
  created_at: string
  updated_at: string
  dweller_strength: number
  dweller_perception: number
  dweller_endurance: number
  dweller_charisma: number
  dweller_intelligence: number
  dweller_agility: number
  dweller_luck: number
  stimpaks: number
  radaways: number
  health?: number
  radiation?: number
  /** Authoritative registry position for spatial runs; absent on legacy runs. */
  pos_x?: number | null
  pos_y?: number | null
}

export interface ExplorationProgress {
  id: string
  status: 'ACTIVE' | 'RETURNING' | 'COMPLETED' | 'RECALLED'
  progress_percentage: number
  time_remaining_seconds: number
  elapsed_time_seconds: number
  return_completes_at?: string | null
  return_time_remaining_seconds?: number
  events: ExplorationEvent[]
  loot_collected: LootItem[]
  stimpaks: number
  radaways: number
}

export interface RewardsSummary {
  caps: number
  caps_credited?: number
  items: LootItem[]
  experience: number
  distance: number
  enemies_defeated: number
  events_encountered: number
  overflow_items?: LootItem[]
  progress_percentage?: number
  recalled_early?: boolean
  exploration_id?: string
  stimpaks?: number
  radaways?: number
  stimpaks_stored?: number
  radaways_stored?: number
}

export interface OverflowResolution {
  caps_granted: number
  unclaimed_loot: LootItem[]
}

export interface PendingOverflow {
  exploration_id: string
  dweller_id: string
  unclaimed_loot: LootItem[]
}

/** Cadence for the shared active-exploration list refresh used by its list surfaces. */
export const ACTIVE_EXPLORATIONS_REFRESH_MS = 15_000

/** Read a 404 from either an `ApiError` (the boundary) or a raw axios error. */
function isNotFoundError(err: unknown): boolean {
  if (typeof err !== 'object' || err === null) return false
  const status =
    (err as { status?: number | null }).status ??
    (err as { response?: { status?: number } }).response?.status
  return status === 404
}

export const useExplorationStore = defineStore('exploration', () => {
  const toast = useToast()
  const { filter: dwellerFilter } = useDwellerStore()
  const authStore = useAuthStore()

  const explorations = ref<Exploration[]>([])
  const activeExplorations = ref<Record<string, Exploration>>({})
  const explorationPartyMap = ref<Record<string, ExplorationPartyMember[]>>({})
  const lastRewards = ref<RewardsSummary | null>(null)
  const pendingSseRewards = ref<{
    rewards: RewardsSummary
    dwellerId: string
    explorationId?: string
  } | null>(null)
  const acknowledgedSseRewards = new Map<string, ReturnType<typeof setTimeout>>()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  let sseInstance: ReturnType<typeof useSse> | null = null
  let sseWatchStop: (() => void) | null = null
  let currentVaultId = ''

  function getExplorationByDwellerId(dwellerId: string) {
    const matches = explorations.value.filter(
      (e) => e.dweller_id === dwellerId && (e.status === 'active' || e.status === 'returning')
    )
    return matches.find((e) => e.status === 'active') ?? matches[0]
  }

  function getActiveExplorationsForVault(vaultId: string) {
    return explorations.value.filter(
      (e) => e.vault_id === vaultId && (e.status === 'active' || e.status === 'returning')
    )
  }

  function upsertExploration(exploration: Exploration): void {
    const index = explorations.value.findIndex((e) => e.id === exploration.id)
    if (index !== -1) explorations.value[index] = exploration
    else explorations.value.push(exploration)

    if (exploration.status === 'active' || exploration.status === 'returning') {
      activeExplorations.value[exploration.id] = exploration
    } else {
      delete activeExplorations.value[exploration.id]
    }
  }

  function startSseSubscription(vaultId: string, token: string): void {
    stopSseSubscription()
    currentVaultId = vaultId

    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    sseInstance = useSse(`${apiBase}/api/v1/stream/exploration/${vaultId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    void sseInstance.start()

    const seenEventKeys = new Set<string>()
    sseWatchStop = watch(
      () => sseInstance?.event.value,
      (evt) => {
        if (!evt || evt.event !== 'exploration') return
        const data = evt.data as Record<string, unknown> | undefined
        if (!data || typeof data.type !== 'string') return
        const explorationId = data.exploration_id as string | undefined
        if (data.type === 'exploration_complete' || data.type === 'exploration_recalled') {
          const rewards = (data.rewards ?? {
            caps: 0,
            items: [],
            experience: 0,
            distance: 0,
          }) as RewardsSummary
          const dwellerId = (data.dweller_id as string) ?? ''
          pendingSseRewards.value = {
            rewards,
            dwellerId,
            ...(explorationId ? { explorationId } : {}),
          }

          if (dwellerId && explorationId) {
            const dweller = dwellerFilter.dwellers.find((d) => d.id === dwellerId)
            const dwellerName = dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller'
            addPendingReport({
              explorationId,
              vaultId: currentVaultId,
              dwellerId,
              dwellerName,
              rewards,
            })
          }
          return
        }

        if (data.type === 'exploration_deleted') {
          // The dweller is gone: close the journey locally without a reward report.
          const closed = explorationId
            ? (activeExplorations.value[explorationId] ??
              explorations.value.find((exploration) => exploration.id === explorationId))
            : undefined
          if (closed) closed.status = 'recalled'
          if (explorationId) delete activeExplorations.value[explorationId]
          return
        }

        if (data.type === 'exploration_returning') {
          const returning = explorationId
            ? (activeExplorations.value[explorationId] ??
              explorations.value.find((e) => e.id === explorationId))
            : undefined
          if (returning) {
            returning.status = 'returning'
            returning.return_started_at =
              (data.return_started_at as string) ?? returning.return_started_at
            returning.return_completes_at =
              (data.return_completes_at as string) ?? returning.return_completes_at
          }
          // A manual recall already toasts from its own action; only the tick-driven
          // finish needs a heads-up here.
          if (!data.recalled) {
            const dweller = dwellerFilter.dwellers.find((d) => d.id === data.dweller_id)
            const dwellerName = dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller'
            toast.info(`${dwellerName} is heading home`)
          }
          return
        }

        const exploration = explorationId
          ? (activeExplorations.value[explorationId] ??
            explorations.value.find((e) => e.id === explorationId))
          : undefined
        if (!exploration) return

        const eventRecord = data.event as ExplorationEvent | undefined
        if (eventRecord?.type && eventRecord.description) {
          const key = `${eventRecord.timestamp}|${eventRecord.type}|${eventRecord.description}`
          if (!seenEventKeys.has(key)) {
            seenEventKeys.add(key)
            exploration.events.push(eventRecord)
            if (eventRecord.type === 'equip') {
              const dwellerId = data.dweller_id
              if (typeof dwellerId === 'string' && dwellerId.length > 0) {
                void dwellerFilter.fetchDwellerDetails(dwellerId, token, true)
              }
              if (!explorationUpdatesDisabled()) {
                const dweller = dwellerFilter.dwellers.find((d) => d.id === data.dweller_id)
                const dwellerName = dweller
                  ? `${dweller.first_name} ${dweller.last_name}`
                  : 'Dweller'
                const description =
                  eventRecord.description.charAt(0).toLowerCase() + eventRecord.description.slice(1)
                toast.info(`${dwellerName} ${description}`)
              }
            }
          }
        }

        if (typeof data.total_caps_found === 'number')
          exploration.total_caps_found = data.total_caps_found
        if (typeof data.enemies_encountered === 'number')
          exploration.enemies_encountered = data.enemies_encountered
        if (typeof data.stimpaks === 'number') exploration.stimpaks = data.stimpaks
        if (typeof data.radaways === 'number') exploration.radaways = data.radaways
        if (typeof data.health === 'number') exploration.health = data.health
        if (typeof data.radiation === 'number') exploration.radiation = data.radiation
      }
    )
  }

  function stopSseSubscription(): void {
    if (sseWatchStop) {
      sseWatchStop()
      sseWatchStop = null
    }
    if (sseInstance) {
      sseInstance.stopReconnect()
      sseInstance.close()
      sseInstance = null
    }
  }

  function clearPendingSseRewards(): void {
    pendingSseRewards.value = null
  }

  function acknowledgeSseReward(dwellerId: string): void {
    const existingTimer = acknowledgedSseRewards.get(dwellerId)
    if (existingTimer) clearTimeout(existingTimer)
    acknowledgedSseRewards.set(
      dwellerId,
      setTimeout(() => acknowledgedSseRewards.delete(dwellerId), 30_000)
    )
  }

  function consumeAcknowledgedSseReward(dwellerId: string): boolean {
    const timer = acknowledgedSseRewards.get(dwellerId)
    if (!timer) return false
    clearTimeout(timer)
    acknowledgedSseRewards.delete(dwellerId)
    return true
  }

  // Actions
  async function sendDwellerToWasteland(
    vaultId: string,
    dwellerId: string,
    duration: number,
    stimpaks: number = 0,
    radaways: number = 0,
    headingDegrees?: number
  ): Promise<Exploration> {
    isLoading.value = true
    error.value = null
    try {
      const body: ExplorationSendRequest = {
        dweller_id: dwellerId,
        duration,
        stimpaks,
        radaways,
      }
      if (headingDegrees !== undefined) body.heading_degrees = headingDegrees
      const exploration = (await explorationApi.sendDwellerToWasteland(
        vaultId,
        body
      )) as unknown as Exploration

      explorations.value.push(exploration)
      activeExplorations.value[exploration.id] = exploration

      return exploration
    } catch (err) {
      handleStoreError(err, 'Failed to send dweller to wasteland')
      error.value = 'Failed to send dweller to wasteland'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function dispatchToLocation(
    vaultId: string,
    dwellerIds: string[],
    locationId: string,
    supplies: { stimpaks: number; radaways: number } = { stimpaks: 0, radaways: 0 }
  ): Promise<Exploration> {
    isLoading.value = true
    error.value = null
    try {
      if (!authStore.token) throw new Error('Not authenticated')
      // The generated schema types events/loot as loose records; the wire payload
      // is the same exploration shape the store already consumes everywhere.
      const exploration = (await explorationApi.dispatchToLocation(vaultId, {
        dwellerIds,
        locationId,
        stimpaks: supplies.stimpaks,
        radaways: supplies.radaways,
      })) as unknown as Exploration
      upsertExploration(exploration)
      return exploration
    } catch (err) {
      handleStoreError(err, 'Failed to dispatch dweller')
      error.value = 'Failed to dispatch dweller'
      throw err
    } finally {
      isLoading.value = false
    }
  }
  async function fetchExplorationsByVault(
    vaultId: string,
    activeOnly = true,
    silent = false
  ): Promise<Exploration[]> {
    if (!silent) {
      isLoading.value = true
      error.value = null
    }
    try {
      const fetched = (await explorationApi.getExplorationsByVault(
        vaultId,
        activeOnly
      )) as unknown as Exploration[]

      explorations.value = fetched
      // Update active explorations map
      activeExplorations.value = {}
      fetched
        .filter((e) => e.status === 'active' || e.status === 'returning')
        .forEach((e) => {
          activeExplorations.value[e.id] = e
        })

      // Deliberate: a silent refresh that succeeds clears a stale error so the
      // next poll can recover the UI. Do not guard this with `!silent`.
      error.value = null
      return fetched
    } catch (err) {
      if (!silent) {
        handleStoreError(err, 'Failed to fetch explorations')
        error.value = 'Failed to fetch explorations'
      }
      throw err
    } finally {
      if (!silent) isLoading.value = false
    }
  }

  async function fetchPartiesForActiveExplorations(vaultId: string): Promise<void> {
    const activeRuns = Object.values(activeExplorations.value)
    const nextPartyMap: Record<string, ExplorationPartyMember[]> = {}
    for (const exploration of activeRuns) {
      try {
        nextPartyMap[exploration.id] = await explorationApi.getExplorationParty(
          vaultId,
          exploration.id
        )
      } catch (err) {
        handleStoreError(
          err,
          `Failed to fetch party for exploration ${exploration.id} in vault ${vaultId}`,
          false
        )
        nextPartyMap[exploration.id] = []
      }
    }
    explorationPartyMap.value = nextPartyMap
  }

  /**
   * Refresh the active exploration list. Initial loads keep the shared loading/error
   * state; polling callers pass `silent` so a background refresh never flaps it.
   */
  async function refreshActiveExplorations(
    vaultId: string,
    options: { includeParties?: boolean; silent?: boolean } = {}
  ): Promise<Exploration[]> {
    const active = await fetchExplorationsByVault(vaultId, true, options.silent ?? false)
    if (options.includeParties) {
      await fetchPartiesForActiveExplorations(vaultId)
    }
    return active
  }

  async function fetchExplorationDetails(explorationId: string): Promise<Exploration> {
    try {
      const exploration = (await explorationApi.getExploration(
        explorationId
      )) as unknown as Exploration

      // Update in explorations list, including direct links to completed runs
      // that are absent from the active-only collection.
      upsertExploration(exploration)

      return exploration
    } catch (err) {
      handleStoreError(err, 'Failed to fetch exploration details')
      throw err
    }
  }

  async function fetchExplorationProgress(explorationId: string): Promise<ExplorationProgress> {
    try {
      return (await explorationApi.getExplorationProgress(
        explorationId
      )) as unknown as ExplorationProgress
    } catch (err) {
      handleStoreError(err, 'Failed to fetch exploration progress')
      throw err
    }
  }

  async function recallDweller(explorationId: string): Promise<ExplorationCompleteResponse> {
    isLoading.value = true
    error.value = null
    try {
      const response = await explorationApi.recallDweller(explorationId)

      if (response.rewards_summary)
        lastRewards.value = response.rewards_summary as unknown as RewardsSummary

      upsertExploration(response.exploration as unknown as Exploration)

      toast.success('Dweller recalled — heading home')
      return response
    } catch (err) {
      handleStoreError(err, 'Failed to recall dweller')
      error.value = 'Failed to recall dweller'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function completeExploration(explorationId: string): Promise<ExplorationCompleteResponse> {
    isLoading.value = true
    error.value = null
    try {
      const response = await explorationApi.completeExploration(explorationId)

      if (response.rewards_summary)
        lastRewards.value = response.rewards_summary as unknown as RewardsSummary

      upsertExploration(response.exploration as unknown as Exploration)

      if (response.rewards_summary) toast.success('Exploration completed successfully!')
      return response
    } catch (err) {
      handleStoreError(err, 'Failed to complete exploration')
      error.value = 'Failed to complete exploration'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function clearError(): void {
    error.value = null
  }

  async function resolveOverflowItem(
    explorationId: string,
    action: 'take' | 'sell',
    index: number
  ): Promise<OverflowResolution> {
    try {
      return (await explorationApi.resolveOverflowItem(
        explorationId,
        action,
        index
      )) as unknown as OverflowResolution
    } catch (err) {
      // Legacy reports are explained by the reward modal instead of a second error toast.
      if (!isNotFoundError(err)) {
        handleStoreError(err, action === 'take' ? 'Could not take item' : 'Could not sell item')
      }
      throw err
    }
  }

  async function fetchPendingOverflow(vaultId: string): Promise<PendingOverflow[]> {
    try {
      return (await explorationApi.getPendingOverflow(vaultId)) as unknown as PendingOverflow[]
    } catch (err) {
      handleStoreError(err, 'Could not load pending exploration loot')
      throw err
    }
  }

  return {
    // State
    explorations,
    activeExplorations,
    explorationPartyMap,
    lastRewards,
    pendingSseRewards,
    isLoading,
    error,
    // Getters
    getExplorationByDwellerId,
    getActiveExplorationsForVault,
    // Actions
    sendDwellerToWasteland,
    dispatchToLocation,
    fetchExplorationsByVault,
    fetchPartiesForActiveExplorations,
    refreshActiveExplorations,
    fetchExplorationDetails,
    fetchExplorationProgress,
    recallDweller,
    completeExploration,
    fetchPendingOverflow,
    resolveOverflowItem,
    startSseSubscription,
    stopSseSubscription,
    clearPendingSseRewards,
    acknowledgeSseReward,
    consumeAcknowledgedSseReward,
    clearError,
  }
})
