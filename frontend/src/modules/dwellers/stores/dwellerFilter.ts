import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'
import {
  DEFAULT_TABLE_COLUMNS,
  DWELLER_TABLE_PRESETS,
  canonicalColumnOrder,
  normalizeTableColumns,
  type DwellerTableColumnId,
} from '@/modules/dwellers/models/dwellerTable'
import {
  getDweller,
  getDwellersByVault,
  type DwellerQueryParams,
} from '@/modules/dwellers/services/dwellerService'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useFeatureFlagsStore } from './featureFlags'

/**
 * Non-null limit for complete-fetch requests (fetchAllDwellers). The backend
 * default limit is 100; this ensures ALL dwellers are returned for dashboard
 * aggregates regardless of vault population.
 */
export const ALL_DWELLERS_FETCH_LIMIT = 1000

export const DWELLER_STATUSES = [
  'idle',
  'working',
  'exploring',
  'questing',
  'training',
  'resting',
  'fighting',
  'dead',
] as const
export type DwellerStatus = (typeof DWELLER_STATUSES)[number]

export const DWELLER_AGE_GROUPS = ['child', 'teen', 'adult', 'all'] as const
export type DwellerAgeGroup = (typeof DWELLER_AGE_GROUPS)[number]

export interface DwellerWithStatus extends DwellerShort {
  status: DwellerStatus
}

export interface DwellerStatusCounts {
  /** Matched dwellers across every status, including dead. */
  all: number
  /** Matched dwellers per status; every status key is present and zero-initialized. */
  byStatus: Record<DwellerStatus, number>
}

export const DWELLER_SORT_KEYS = [
  'name',
  'level',
  'happiness',
  'strength',
  'perception',
  'endurance',
  'charisma',
  'intelligence',
  'agility',
  'luck',
] as const
export type DwellerSortBy = (typeof DWELLER_SORT_KEYS)[number]

export const SORT_DIRECTIONS = ['asc', 'desc'] as const
export type SortDirection = (typeof SORT_DIRECTIONS)[number]

export const isDwellerStatus = (value: unknown): value is DwellerStatus =>
  typeof value === 'string' && (DWELLER_STATUSES as readonly string[]).includes(value)

export const isDwellerAgeGroup = (value: unknown): value is DwellerAgeGroup =>
  typeof value === 'string' && (DWELLER_AGE_GROUPS as readonly string[]).includes(value)

export const isDwellerSortBy = (value: unknown): value is DwellerSortBy =>
  typeof value === 'string' && (DWELLER_SORT_KEYS as readonly string[]).includes(value)

export const isSortDirection = (value: unknown): value is SortDirection =>
  typeof value === 'string' && (SORT_DIRECTIONS as readonly string[]).includes(value)

/**
 * Roster ordering, shared by the store and the unassigned panel. The second copy that
 * lived in UnassignedDwellers had already drifted on how a missing stat sorts.
 */
export function compareDwellers(
  a: DwellerShort,
  b: DwellerShort,
  sortBy: DwellerSortBy,
  direction: SortDirection
): number {
  const comparison =
    sortBy === 'name'
      ? `${a.first_name} ${a.last_name}`
          .toLowerCase()
          .localeCompare(`${b.first_name} ${b.last_name}`.toLowerCase())
      : (a[sortBy] ?? 0) - (b[sortBy] ?? 0)

  return direction === 'asc' ? comparison : -comparison
}

/** `all` means unfiltered, so the roster and the facet counts share one definition. */
export function matchesAgeGroup(dweller: DwellerShort, ageGroup: DwellerAgeGroup): boolean {
  return ageGroup === 'all' || dweller.age_group === ageGroup
}
export type DwellerViewMode = 'list' | 'grid' | 'table'
type DwellerFetchOptions = {
  status?: DwellerStatus | 'all'
  ageGroup?: DwellerAgeGroup
  race?: string
  faction?: string
  search?: string
  sortBy?: string
  order?: 'asc' | 'desc'
  skip?: number
  limit?: number
  signal?: AbortSignal
}

export const useDwellerFilterStore = defineStore('dwellerFilter', () => {
  // State
  const dwellers = ref<DwellerShort[]>([])
  const allDwellers = ref<DwellerShort[]>([])
  const detailedDwellers = ref<Record<string, Dweller | null>>({})
  let dwellersRequestSeq = 0

  function toQueryParams(options: DwellerFetchOptions = {}): DwellerQueryParams {
    return {
      status: options.status !== 'all' ? options.status : undefined,
      ageGroup: options.ageGroup !== 'all' ? options.ageGroup : undefined,
      race: options.race !== 'all' ? options.race : undefined,
      faction: options.faction !== 'all' ? options.faction : undefined,
      search: options.search,
      sortBy: options.sortBy,
      order: options.order,
      skip: options.skip,
      limit: options.limit,
      signal: options.signal,
    }
  }

  const { run: runFetchDwellers, isLoading } = useAsyncAction(
    async (vaultId: string, token: string, options?: DwellerFetchOptions) => {
      const requestSeq = ++dwellersRequestSeq
      const data = await getDwellersByVault(vaultId, token, toQueryParams(options))
      if (requestSeq === dwellersRequestSeq) {
        dwellers.value = data
      }
    },
    { context: 'Failed to fetch dwellers', showToast: false }
  )

  const featureFlags = useFeatureFlagsStore()

  // Vault-scoped request tracking for fetchAllDwellers: results are applied
  // only when they still match the active vault and the latest request.
  let allDwellersVaultId: string | null = null
  let allDwellersRequestSeq = 0

  // Filter and sort state (persisted in localStorage)
  const filterStatus = useLocalStorage<DwellerStatus | 'all'>('dwellerFilterStatus', 'all')
  const filterAgeGroup = useLocalStorage<DwellerAgeGroup>('dwellerFilterAgeGroup', 'all')
  // Identity lives in visual_attributes; 'all' means unfiltered.
  const filterRace = useLocalStorage<string>('dwellerFilterRace', 'all')
  const filterFaction = useLocalStorage<string>('dwellerFilterFaction', 'all')
  const sortBy = useLocalStorage<DwellerSortBy>('dwellerSortBy', 'name')
  const sortDirection = useLocalStorage<SortDirection>('dwellerSortDirection', 'asc')
  const viewMode = useLocalStorage<DwellerViewMode>('dwellerViewMode', 'list')
  const tableColumns = useLocalStorage<DwellerTableColumnId[]>(
    'dwellerTableColumns',
    DEFAULT_TABLE_COLUMNS,
    {
      serializer: {
        read: (raw) => normalizeTableColumns(JSON.parse(raw) as unknown),
        write: (value) => JSON.stringify(value),
      },
    }
  )

  /**
   * Get dweller status - now directly from backend
   */
  function getDwellerStatus(dwellerId: string): DwellerStatus | null {
    const dweller = dwellers.value.find((d) => d.id === dwellerId)
    if (!dweller) return null

    // Backend now provides status directly
    return (dweller.status as DwellerStatus) || 'idle'
  }

  /**
   * Get all dwellers with their status (already provided by backend)
   */
  const dwellersWithStatus = computed((): DwellerWithStatus[] => {
    return dwellers.value.map((dweller) => ({
      ...dweller,
      status: (dweller.status as DwellerStatus) || 'idle',
    }))
  })

  /**
   * Get dwellers filtered by status - filters are now applied on backend
   */
  function getDwellersByStatus(status: DwellerStatus): DwellerWithStatus[] {
    return dwellers.value
      .filter((dweller) => dweller.status === status)
      .map((dweller) => ({
        ...dweller,
        status: (dweller.status as DwellerStatus) || 'idle',
      }))
  }

  /**
   * Get filtered and sorted dwellers based on current filter/sort settings
   */
  const filteredAndSortedDwellers = computed((): DwellerWithStatus[] => {
    let result = dwellersWithStatus.value

    // Apply status filter
    if (filterStatus.value !== 'all') {
      result = result.filter((dweller) => dweller.status === filterStatus.value)
    }

    // Apply identity filters
    if (filterRace.value !== 'all') {
      result = result.filter((dweller) => dweller.visual_attributes?.race === filterRace.value)
    }
    if (featureFlags.factionMechanics && filterFaction.value !== 'all') {
      result = result.filter(
        (dweller) => dweller.visual_attributes?.faction === filterFaction.value
      )
    }

    // Apply sorting
    result = [...result].sort((a, b) => compareDwellers(a, b, sortBy.value, sortDirection.value))

    return result
  })

  /**
   * Count every status under the given non-status filters, from the unfiltered
   * allDwellers collection. The backend-narrowed `dwellers` list would only ever
   * report the currently selected status, so a chip could not preview its own result.
   */
  function countByStatus(filters: {
    ageGroup: DwellerAgeGroup
    race: string
    faction: string
  }): DwellerStatusCounts {
    const byStatus = Object.fromEntries(DWELLER_STATUSES.map((status) => [status, 0])) as Record<
      DwellerStatus,
      number
    >
    const factionActive = featureFlags.factionMechanics && filters.faction !== 'all'
    let all = 0

    for (const dweller of allDwellers.value) {
      if (!matchesAgeGroup(dweller, filters.ageGroup)) continue
      if (filters.race !== 'all' && dweller.visual_attributes?.race !== filters.race) continue
      if (factionActive && dweller.visual_attributes?.faction !== filters.faction) continue

      const status = isDwellerStatus(dweller.status) ? dweller.status : 'idle'
      byStatus[status] += 1
      all += 1
    }

    return { all, byStatus }
  }

  async function fetchDwellersByVault(
    vaultId: string,
    token: string,
    options?: DwellerFetchOptions
  ): Promise<void> {
    await runFetchDwellers(vaultId, token, options)
  }

  async function fetchWithCurrentFilters(
    vaultId: string,
    token: string,
    options: DwellerFetchOptions = {}
  ): Promise<void> {
    await fetchDwellersByVault(vaultId, token, {
      ...options,
      status: filterStatus.value,
      ageGroup: filterAgeGroup.value,
      race: filterRace.value,
      // The API rejects a faction filter while the switch is off, so never send it.
      faction: featureFlags.factionMechanics ? filterFaction.value : 'all',
      sortBy: sortBy.value,
      order: sortDirection.value,
    })
  }

  /**
   * Fetch ALL dwellers for a vault without any filters (for dashboard aggregates).
   * Populates the allDwellers ref without touching the filtered dwellers list.
   */
  async function fetchAllDwellers(vaultId: string, token: string): Promise<void> {
    allDwellers.value = []
    allDwellersVaultId = vaultId
    const requestSeq = ++allDwellersRequestSeq

    try {
      const data = await getDwellersByVault(vaultId, token, {
        skip: 0,
        limit: ALL_DWELLERS_FETCH_LIMIT,
      })
      if (requestSeq === allDwellersRequestSeq && allDwellersVaultId === vaultId) {
        allDwellers.value = data
      }
    } catch (error) {
      handleStoreError(error, `Failed to fetch all dwellers for vault ${vaultId}`)
    }
  }

  async function fetchDwellerDetails(
    id: string,
    token: string,
    forceRefresh = false
  ): Promise<Dweller | null> {
    // Guard against invalid IDs (e.g. undefined before route resolves)
    if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      return null
    }
    if (detailedDwellers.value[id] && !forceRefresh) return detailedDwellers.value[id] ?? null
    try {
      const dweller = await getDweller(id, token)
      detailedDwellers.value[id] = dweller
      return dweller
    } catch (error) {
      handleStoreError(error, `Failed to fetch details for dweller ${id}`)
      return null
    }
  }

  function setFilterStatus(status: DwellerStatus | 'all'): void {
    filterStatus.value = status
  }

  function setFilterAgeGroup(ageGroup: DwellerAgeGroup): void {
    filterAgeGroup.value = ageGroup
  }

  function setFilterRace(race: string): void {
    filterRace.value = race
  }

  function setFilterFaction(faction: string): void {
    filterFaction.value = faction
  }

  function setSortBy(sort: DwellerSortBy): void {
    sortBy.value = sort
  }

  function setSortDirection(direction: SortDirection): void {
    sortDirection.value = direction
  }

  function setViewMode(mode: DwellerViewMode): void {
    viewMode.value = mode
  }

  function toggleTableColumn(columnId: DwellerTableColumnId): void {
    const next = tableColumns.value.includes(columnId)
      ? tableColumns.value.filter((id) => id !== columnId)
      : [...tableColumns.value, columnId]
    if (next.length === 0) return
    tableColumns.value = canonicalColumnOrder(next)
  }

  function applyTablePreset(presetId: string): void {
    const preset = DWELLER_TABLE_PRESETS.find((item) => item.id === presetId)
    if (preset) tableColumns.value = canonicalColumnOrder(preset.columns)
  }

  function resetTableColumns(): void {
    tableColumns.value = [...DEFAULT_TABLE_COLUMNS]
  }

  return {
    dwellers,
    allDwellers,
    dwellersWithStatus,
    detailedDwellers,
    isLoading,
    filterStatus,
    filterAgeGroup,
    filterRace,
    filterFaction,
    sortBy,
    sortDirection,
    viewMode,
    tableColumns,
    getDwellerStatus,
    getDwellersByStatus,
    filteredAndSortedDwellers,
    countByStatus,
    fetchDwellersByVault,
    fetchWithCurrentFilters,
    fetchAllDwellers,
    fetchDwellerDetails,
    setFilterStatus,
    setFilterAgeGroup,
    setFilterRace,
    setFilterFaction,
    setSortBy,
    setSortDirection,
    setViewMode,
    toggleTableColumn,
    applyTablePreset,
    resetTableColumns,
  }
})
