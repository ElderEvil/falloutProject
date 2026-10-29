import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { components } from '@/core/types/api.generated'
import type {
  Room,
  RoomBuild,
  RoomRushQuote,
  RoomRushResult,
  RoomStyleValue,
  RoomTemplate,
} from '../models/room'
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
      await useVaultStore().refreshVault(vaultId, token)
    } catch (error) {
      handleStoreError(error, context)
    }
  }

  // Actions
  async function fetchRooms(vaultId: string, throwOnError = false): Promise<FetchRoomsResult> {
    const requestSequence = ++fetchRoomsRequestSequence

    try {
      // Every room occupies at least one unit, so this covers the entire grid.
      const fetched = await roomApi.getByVault(vaultId, floorUnits.value * (yMax.value + 1))
      if (requestSequence !== fetchRoomsRequestSequence) return 'superseded'
      rooms.value = fetched
      roomsLoadedVaultId.value = vaultId
      return 'loaded'
    } catch (error) {
      handleStoreError(error, 'Failed to fetch rooms')
      if (requestSequence !== fetchRoomsRequestSequence) return 'superseded'
      rooms.value = [] // Reset to empty array on error
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

  async function buildRoom(
    roomName: string,
    coordinateX: number,
    coordinateY: number,
    vaultId: string
  ): Promise<'built' | 'extended'> {
    let result: 'built' | 'extended' = 'built'
    try {
      const roomData: RoomBuild = {
        vault_id: vaultId,
        room_name: roomName,
        coordinate_x: coordinateX,
        coordinate_y: coordinateY,
      }
      const built = await roomApi.build(roomData)
      const existingIndex = rooms.value.findIndex((room) => room.id === built.id)
      if (existingIndex !== -1) {
        rooms.value[existingIndex] = built
        result = 'extended'
      } else {
        rooms.value.push(built)
        result = 'built'
      }
    } catch (error) {
      handleStoreError(error, 'Failed to build room')
      if (error instanceof ApiError && typeof error.detail === 'string') {
        throw new Error(error.detail, { cause: error })
      }
      throw error
    }
    // Refresh vault to update caps (non-throwing)
    await refreshVaultSafely(vaultId, 'Failed to refresh vault after building room')
    // A merge can absorb several rooms, so resync the list instead of trusting one response.
    await fetchRooms(vaultId)
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
    // Refresh vault to update caps after refund (non-throwing)
    await refreshVaultSafely(vaultId, 'Failed to refresh vault after destroying room')
  }

  async function upgradeRoom(roomId: string, vaultId: string): Promise<void> {
    try {
      const survivor = await roomApi.upgrade(roomId)

      // The backend returns the merge survivor, which may be a different room:
      // resync instead of patching one entry so absorbed rooms disappear.
      const previousSize = rooms.value.find((room) => room.id === roomId)?.size ?? 0
      await fetchRooms(vaultId)
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
      refreshes.push(dwellers.fetchDwellersByVault(vaultId, token))
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
