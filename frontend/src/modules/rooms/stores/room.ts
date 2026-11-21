import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { components } from '@/core/types/api.generated'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type {
  Room,
  RoomBuild,
  RoomRushQuote,
  RoomRushResult,
  RoomStyleValue,
  RoomTemplate,
} from '../models/room'
import { roomStyle } from '../models/room'
import { roomApi } from '../api/room'
import {
  FLOOR_UNITS,
  ROOM_SLOT_STARTS,
  SHAFT_X,
  UNITS_PER_ROOM,
  BUILD_Y_MAX,
  Y_MAX,
} from '../models/grid'
import { handleStoreError } from '@/core/utils/errorHandler'
import { ApiError } from '@/core/utils/api'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import { audioManager } from '@/core/audio/audioManager'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'

type GridConfig = components['schemas']['GridConfig']

/** Outcome of a room fetch: whose data (if any) now owns the store state. */
export type FetchRoomsResult = 'loaded' | 'superseded' | 'failed'

export const useRoomStore = defineStore('room', () => {
  const authStore = useAuthStore()
  // State
  const rooms = ref<Room[]>([])
  const roomsLoadedVaultId = ref<string | null>(null)
  const gridConfig = ref<GridConfig | null>(null)
  const availableRooms = ref<RoomTemplate[]>([])
  const selectedRoom = ref<RoomTemplate | null>(null)
  const isPlacingRoom = ref(false)
  // Survivor room id briefly highlighted after an upgrade absorbs a neighbour.
  const mergedRoomId = ref<string | null>(null)
  const rushedRoomId = ref<string | null>(null)
  const rushOutcome = ref<'success' | 'failure' | null>(null)
  let fetchRoomsRequestSequence = 0
  let fetchBuildableRoomsRequestSequence = 0
  let mergedHighlightTimeout: ReturnType<typeof setTimeout> | null = null
  let rushHighlightTimeout: ReturnType<typeof setTimeout> | null = null

  // Background vault refresh — non-throwing, while still surfacing failures consistently.
  async function refreshVaultSafely(vaultId: string, context: string) {
    const token = authStore.token
    if (!token) return
    try {
      await useVaultStore().refreshVault(vaultId)
    } catch (error) {
      handleStoreError(error, context)
    }
  }

  // Actions

  async function refreshDwellerAssignments(
    vaultId: string,
    roomsReady?: Promise<unknown>
  ): Promise<void> {
    const token = authStore.token
    const vaultStore = useVaultStore()
    const generation = vaultStore.currentSessionGeneration()
    if (!token) return
    if (vaultStore.activeVaultId && vaultStore.activeVaultId !== vaultId) return
    const { useDwellerStore } = await import('@/modules/dwellers/stores/dweller')
    const { filter } = useDwellerStore()
    // Roster first: tiles switch to it before a filtered page replacement lands.
    await Promise.allSettled([filter.fetchAllDwellers(vaultId, false, true)])
    await Promise.allSettled([filter.fetchWithCurrentFilters(vaultId)])
    await roomsReady
    const activeVaultId = vaultStore.activeVaultId
    if (
      (activeVaultId && activeVaultId !== vaultId) ||
      vaultStore.currentSessionGeneration() !== generation
    )
      return
    const freshById = new Map(filter.allDwellers.map((dweller) => [dweller.id, dweller]))
    const roomById = new Map(rooms.value.map((room) => [room.id, room]))
    for (const [id, detailed] of Object.entries(filter.detailedDwellers)) {
      const fresh = freshById.get(id)
      if (!detailed || !fresh) continue
      const nextRoom = fresh.room_id ? (roomById.get(fresh.room_id) ?? null) : null
      if (detailed.room?.id !== nextRoom?.id) {
        filter.detailedDwellers[id] = { ...detailed, room: nextRoom }
      }
    }
  }

  async function fetchRooms(vaultId: string, throwOnError = false): Promise<FetchRoomsResult> {
    // An off-vault read must not supersede the active vault's read or publish a foreign layout.
    const activeVaultId = useVaultStore().activeVaultId
    if (activeVaultId && activeVaultId !== vaultId) return 'superseded'
    const requestSequence = ++fetchRoomsRequestSequence
    const generation = authStore.sessionGeneration
    const stale = () => {
      const nowActive = useVaultStore().activeVaultId
      return (
        requestSequence !== fetchRoomsRequestSequence ||
        (nowActive !== null && nowActive !== vaultId) ||
        authStore.sessionGeneration !== generation
      )
    }
    try {
      // Every room occupies at least one unit, so this covers the entire grid.
      const fetched = await roomApi.getByVault(vaultId, floorUnits.value * (yMax.value + 1))
      if (stale()) return 'superseded'
      rooms.value = fetched
      roomsLoadedVaultId.value = vaultId
      return 'loaded'
    } catch (error) {
      if (stale()) return 'superseded'
      handleStoreError(error, 'Failed to fetch rooms')
      rooms.value = [] // Reset to empty array on error
      roomsLoadedVaultId.value = null
      if (throwOnError) throw error
      return 'failed'
    }
  }

  async function fetchBuildableRooms(vaultId: string): Promise<void> {
    const requestSequence = ++fetchBuildableRoomsRequestSequence

    try {
      const fetched = await roomApi.getBuildable(vaultId)
      if (requestSequence === fetchBuildableRoomsRequestSequence) {
        availableRooms.value = fetched
      }
    } catch (error) {
      handleStoreError(error, 'Failed to fetch rooms data')
      if (requestSequence === fetchBuildableRoomsRequestSequence) {
        availableRooms.value = []
      }
    }
  }

  // The backend merges the same name/tier/style component and the survivor keeps the candidate's id,
  // so every such room inside the survivor's span was absorbed.
  function absorbMergeNeighbours(built: Room): Room[] {
    const builtStart = built.coordinate_x ?? 0
    const builtEnd = builtStart + (built.size ?? built.size_min)
    return rooms.value.filter(
      (room) =>
        room.id !== built.id &&
        room.name === built.name &&
        room.coordinate_y === built.coordinate_y &&
        (room.tier ?? 1) === (built.tier ?? 1) &&
        roomStyle(room) === roomStyle(built) &&
        (room.coordinate_x ?? 0) >= builtStart &&
        (room.coordinate_x ?? 0) + (room.size ?? room.size_min) <= builtEnd
    )
  }

  async function buildRoom(
    roomName: string,
    coordinateX: number,
    coordinateY: number,
    vaultId: string
  ): Promise<'built' | 'extended'> {
    const vaultStore = useVaultStore()
    const generation = vaultStore.currentSessionGeneration()
    const { useDwellerStore } = await import('@/modules/dwellers/stores/dweller')
    const { filter } = useDwellerStore()
    let result: 'built' | 'extended' = 'built'
    try {
      const roomData: RoomBuild = {
        vault_id: vaultId,
        room_name: roomName,
        coordinate_x: coordinateX,
        coordinate_y: coordinateY,
      }
      const built = await roomApi.build(roomData)
      if (
        (vaultStore.activeVaultId && vaultStore.activeVaultId !== vaultId) ||
        vaultStore.currentSessionGeneration() !== generation
      )
        return result
      // Publish the survivor and its repointed occupants together or the absorbed tile blanks.
      const absorbed = roomsLoadedVaultId.value === vaultId ? absorbMergeNeighbours(built) : []
      const absorbedIds = new Set(absorbed.map((room) => room.id))
      const repoint = (dweller: DwellerShort): DwellerShort =>
        dweller.room_id && absorbedIds.has(dweller.room_id)
          ? { ...dweller, room_id: built.id }
          : dweller
      filter.dwellers = filter.dwellers.map(repoint)
      filter.allDwellers = filter.allDwellers.map(repoint)
      for (const [id, detailed] of Object.entries(filter.detailedDwellers)) {
        if (detailed?.room && absorbedIds.has(detailed.room.id)) {
          filter.detailedDwellers[id] = { ...detailed, room: built }
        }
      }
      rooms.value = rooms.value.filter((room) => !absorbedIds.has(room.id))
      const index = rooms.value.findIndex((room) => room.id === built.id)
      if (index !== -1) {
        rooms.value[index] = built
        result = 'extended'
      } else if (absorbedIds.size > 0 || (built.size ?? built.size_min) > built.size_min) {
        rooms.value = rooms.value.concat(built)
        result = 'extended'
      } else {
        rooms.value.push(built)
      }
    } catch (error) {
      handleStoreError(error, 'Failed to build room')
      if (error instanceof ApiError && typeof error.detail === 'string') {
        throw new Error(error.detail, { cause: error })
      }
      throw error
    }
    // A merge absorbs rooms and reassigns their dwellers, so resync both lists
    // instead of leaving dwellers pointing at a deleted room.
    await refreshVaultSafely(vaultId, 'Failed to refresh vault after building room')
    const roomsReady = fetchRooms(vaultId)
    await Promise.all([roomsReady, refreshDwellerAssignments(vaultId, roomsReady)])
    audioManager.play('vaultBuild', 'sfx')
    return result
  }

  async function destroyRoom(roomId: string, vaultId: string): Promise<void> {
    try {
      await roomApi.destroy(roomId)
      rooms.value = rooms.value.filter((room) => room.id !== roomId)
    } catch (error) {
      handleStoreError(error, 'Failed to destroy room')
      if (error instanceof ApiError && typeof error.detail === 'string') {
        throw new Error(error.detail, { cause: error })
      }
      throw error
    }
    await Promise.all([
      refreshVaultSafely(vaultId, 'Failed to refresh vault after destroying room'),
      refreshDwellerAssignments(vaultId),
    ])
  }

  async function upgradeRoom(roomId: string, vaultId: string): Promise<void> {
    try {
      const survivor = await roomApi.upgrade(roomId)

      // The backend returns the merge survivor, which may be a different room:
      // resync instead of patching one entry so absorbed rooms disappear.
      const previousSize = rooms.value.find((room) => room.id === roomId)?.size ?? 0
      const roomsReady = fetchRooms(vaultId)
      await Promise.all([roomsReady, refreshDwellerAssignments(vaultId, roomsReady)])
      if (survivor.id !== roomId || (survivor.size ?? 0) > previousSize) {
        flashMergedRoom(survivor.id)
      }
    } catch (error) {
      handleStoreError(error, 'Failed to upgrade room')
      if (error instanceof ApiError && typeof error.detail === 'string') {
        throw new Error(error.detail, { cause: error })
      }
      throw error
    }
    audioManager.play('upgrade', 'sfx')
    // Refresh vault to update caps (non-throwing)
    await refreshVaultSafely(vaultId, 'Failed to refresh vault after upgrading room')
  }

  async function remodelRoom(roomId: string, otherRoomId?: string): Promise<void> {
    const result = await roomApi.remodel(roomId, otherRoomId)
    const replacements = Array.isArray(result) ? result : [result]
    rooms.value = rooms.value
      .filter((room) => room.id !== roomId && room.id !== otherRoomId)
      .concat(replacements)
    const vaultId = useVaultStore().activeVaultId
    if (vaultId) await refreshDwellerAssignments(vaultId)
    if (otherRoomId) flashMergedRoom(replacements[0]!.id)
    audioManager.play('vaultBuild', 'sfx')
  }

  async function applyRoomStyle(roomId: string, style: RoomStyleValue): Promise<Room> {
    try {
      const styled = await roomApi.applyStyle(roomId, style)
      const index = rooms.value.findIndex((room) => room.id === roomId)
      if (index !== -1) rooms.value[index] = styled
      return styled
    } catch (error) {
      handleStoreError(error, 'Failed to apply room style')
      if (error instanceof ApiError && typeof error.detail === 'string') {
        throw new Error(error.detail, { cause: error })
      }
      throw error
    }
  }

  async function fetchRushQuote(roomId: string): Promise<RoomRushQuote> {
    return roomApi.getRushQuote(roomId)
  }

  async function refreshRushDependents(vaultId: string, incidentId: string | null): Promise<void> {
    const token = authStore.token
    if (!token) return
    const [{ useDwellerStore }, { useStorageStore }, { useIncidentStore }] = await Promise.all([
      import('@/modules/dwellers/stores/dweller'),
      import('@/modules/storage/stores/storage'),
      import('@/modules/combat/stores/incident'),
    ])
    const { filter: dwellers } = useDwellerStore()
    const storage = useStorageStore()
    const incidentStore = useIncidentStore()
    const refreshes: Promise<unknown>[] = [
      refreshVaultSafely(vaultId, 'Failed to refresh vault after rushing room'),
    ]
    if (dwellers.dwellers.length > 0) {
      refreshes.push(dwellers.fetchDwellersByVault(vaultId))
    }
    if (storage.vaultId === vaultId) {
      refreshes.push(storage.refresh(vaultId))
    }
    if (incidentId) {
      incidentStore.watchPendingIncident(vaultId, incidentId, token)
      refreshes.push(incidentStore.fetchIncidents(vaultId, token))
    }
    await Promise.allSettled(refreshes)
  }

  async function rushRoom(roomId: string, vaultId: string): Promise<RoomRushResult> {
    const result = await roomApi.rush(roomId)
    setTimeout(() => flashRushedRoom(roomId, result.outcome), FEEDBACK_TIMING_MS.rushDelay)
    void refreshRushDependents(vaultId, result.incident_id).catch((error) => {
      handleStoreError(error, 'Failed to refresh vault after rushing room')
    })
    return result
  }

  function flashMergedRoom(roomId: string): void {
    mergedRoomId.value = roomId
    if (mergedHighlightTimeout !== null) clearTimeout(mergedHighlightTimeout)
    mergedHighlightTimeout = setTimeout(() => {
      if (mergedRoomId.value === roomId) mergedRoomId.value = null
    }, 1200)
  }

  function flashRushedRoom(roomId: string, outcome: 'success' | 'failure'): void {
    rushedRoomId.value = roomId
    rushOutcome.value = outcome
    if (rushHighlightTimeout !== null) clearTimeout(rushHighlightTimeout)
    rushHighlightTimeout = setTimeout(() => {
      if (rushedRoomId.value === roomId) {
        rushedRoomId.value = null
        rushOutcome.value = null
      }
    }, 1400)
  }

  function selectRoom(room: RoomTemplate): void {
    selectedRoom.value = room
    isPlacingRoom.value = true
  }

  function deselectRoom(): void {
    selectedRoom.value = null
    isPlacingRoom.value = false
  }

  // Grid geometry is owned by the backend; local defaults cover the first paint.
  const floorUnits = computed(() => gridConfig.value?.floor_units ?? FLOOR_UNITS)
  const shaftX = computed(() => gridConfig.value?.shaft_x ?? SHAFT_X)
  const unitsPerRoom = computed(() => gridConfig.value?.units_per_room ?? UNITS_PER_ROOM)
  const roomSlotStarts = computed(() => {
    const config = gridConfig.value
    return config
      ? [...config.left_slot_starts, ...config.right_slot_starts]
      : [...ROOM_SLOT_STARTS]
  })
  const buildYMax = computed(() => gridConfig.value?.build_y_max ?? BUILD_Y_MAX)
  const yMax = computed(() => gridConfig.value?.y_max ?? Y_MAX)

  async function fetchGridConfig(): Promise<void> {
    try {
      gridConfig.value = await roomApi.getGridConfig()
    } catch (error) {
      handleStoreError(error, 'Failed to fetch grid config')
    }
  }

  return {
    // State
    rooms,
    roomsLoadedVaultId,
    gridConfig,
    availableRooms,
    selectedRoom,
    isPlacingRoom,
    mergedRoomId,
    rushedRoomId,
    rushOutcome,
    floorUnits,
    shaftX,
    unitsPerRoom,
    roomSlotStarts,
    buildYMax,
    yMax,
    // Actions
    fetchRooms,
    fetchGridConfig,
    fetchBuildableRooms,
    buildRoom,
    destroyRoom,
    upgradeRoom,
    applyRoomStyle,
    remodelRoom,
    fetchRushQuote,
    rushRoom,
    selectRoom,
    deselectRoom,
  }
})
