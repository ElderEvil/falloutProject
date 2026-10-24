import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import { AxiosError } from 'axios'
import type { components } from '@/core/types/api.generated'
import type {
  Room,
  RoomBuild,
  RoomRushQuote,
  RoomRushResult,
  RoomStyleValue,
  RoomTemplate,
} from '../models/room'
import {
  FLOOR_UNITS,
  ROOM_SLOT_STARTS,
  SHAFT_X,
  UNITS_PER_ROOM,
  BUILD_Y_MAX,
  Y_MAX,
} from '../models/grid'
import { handleStoreError } from '@/core/utils/errorHandler'
import { apiGet, apiPost } from '@/core/utils/api'
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
  async function refreshVaultSafely(vaultId: string, token: string, context: string) {
    try {
      await useVaultStore().refreshVault(vaultId, token)
    } catch (error) {
      handleStoreError(error, context)
    }
  }

  // Actions
  async function fetchRooms(
    vaultId: string,
    token: string,
    throwOnError = false
  ): Promise<FetchRoomsResult> {
    const requestSequence = ++fetchRoomsRequestSequence

    try {
      const response = await axios.get<Room[]>(`/api/v1/rooms/vault/${vaultId}/`, {
        // Every room occupies at least one unit, so this covers the entire grid.
        params: { limit: floorUnits.value * (yMax.value + 1) },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (requestSequence !== fetchRoomsRequestSequence) return 'superseded'
      rooms.value = response.data
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

  async function fetchBuildableRooms(token: string, vaultId: string): Promise<void> {
    const requestSequence = ++fetchBuildableRoomsRequestSequence

    try {
      const response = await axios.get<RoomTemplate[]>(`/api/v1/rooms/buildable/${vaultId}/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (requestSequence === fetchBuildableRoomsRequestSequence) {
        availableRooms.value = response.data
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
    token: string,
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
      const response = await axios.post<Room>('/api/v1/rooms/build/', roomData, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const existingIndex = rooms.value.findIndex((room) => room.id === response.data.id)
      if (existingIndex !== -1) {
        rooms.value[existingIndex] = response.data
        result = 'extended'
      } else {
        rooms.value.push(response.data)
        result = 'built'
      }
    } catch (error) {
      handleStoreError(error, 'Failed to build room')
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail, { cause: error })
      }
      throw error
    }
    // Refresh vault to update caps (non-throwing)
    await refreshVaultSafely(vaultId, token, 'Failed to refresh vault after building room')
    // A merge can absorb several rooms, so resync the list instead of trusting one response.
    await fetchRooms(vaultId, token)
    audioManager.play('vaultBuild', 'sfx')
    return result
  }

  async function destroyRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      await axios.delete(`/api/v1/rooms/destroy/${roomId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      rooms.value = rooms.value.filter((room) => room.id !== roomId)
    } catch (error) {
      handleStoreError(error, 'Failed to destroy room')
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail, { cause: error })
      }
      throw error
    }
    // Refresh vault to update caps after refund (non-throwing)
    await refreshVaultSafely(vaultId, token, 'Failed to refresh vault after destroying room')
  }

  async function upgradeRoom(roomId: string, token: string, vaultId: string): Promise<void> {
    try {
      const response = await axios.post<Room>(
        `/api/v1/rooms/upgrade/${roomId}`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // The backend returns the merge survivor, which may be a different room:
      // resync instead of patching one entry so absorbed rooms disappear.
      const previousSize = rooms.value.find((room) => room.id === roomId)?.size ?? 0
      await fetchRooms(vaultId, token)
      const survivor = response.data
      if (survivor.id !== roomId || (survivor.size ?? 0) > previousSize) {
        flashMergedRoom(survivor.id)
      }
    } catch (error) {
      handleStoreError(error, 'Failed to upgrade room')
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail, { cause: error })
      }
      throw error
    }
    audioManager.play('upgrade', 'sfx')
    // Refresh vault to update caps (non-throwing)
    await refreshVaultSafely(vaultId, token, 'Failed to refresh vault after upgrading room')
  }

  async function remodelRoom(roomId: string, token: string, otherRoomId?: string): Promise<void> {
    const action = otherRoomId ? 'merge' : 'split'
    const response = await axios.post<Room | Room[]>(
      `/api/v1/rooms/${action}/${roomId}`,
      otherRoomId ? { other_room_id: otherRoomId } : {},
      { headers: { Authorization: `Bearer ${token}` } }
    )
    const replacements = Array.isArray(response.data) ? response.data : [response.data]
    rooms.value = rooms.value
      .filter((room) => room.id !== roomId && room.id !== otherRoomId)
      .concat(replacements)
    if (otherRoomId) flashMergedRoom(replacements[0]!.id)
    audioManager.play('vaultBuild', 'sfx')
  }

  async function applyRoomStyle(
    roomId: string,
    style: RoomStyleValue,
    token: string
  ): Promise<Room> {
    try {
      const response = await axios.post<Room>(
        `/api/v1/rooms/style/${roomId}`,
        { style },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      const index = rooms.value.findIndex((room) => room.id === roomId)
      if (index !== -1) rooms.value[index] = response.data
      return response.data
    } catch (error) {
      handleStoreError(error, 'Failed to apply room style')
      if (error instanceof AxiosError && error.response?.data?.detail) {
        throw new Error(error.response.data.detail, { cause: error })
      }
      throw error
    }
  }

  async function fetchRushQuote(roomId: string): Promise<RoomRushQuote> {
    return apiGet<RoomRushQuote>(`/api/v1/rooms/${roomId}/rush`)
  }

  async function refreshRushDependents(
    vaultId: string,
    token: string,
    incidentId: string | null
  ): Promise<void> {
    const [{ useDwellerStore }, { useStorageStore }, { useIncidentStore }] = await Promise.all([
      import('@/modules/dwellers/stores/dweller'),
      import('@/modules/storage/stores/storage'),
      import('@/modules/combat/stores/incident'),
    ])
    const { filter: dwellers } = useDwellerStore()
    const storage = useStorageStore()
    const incidentStore = useIncidentStore()
    const refreshes: Promise<unknown>[] = [
      refreshVaultSafely(vaultId, token, 'Failed to refresh vault after rushing room'),
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
    const result = await apiPost<RoomRushResult>(`/api/v1/rooms/${roomId}/rush`, {})
    setTimeout(() => flashRushedRoom(roomId, result.outcome), FEEDBACK_TIMING_MS.rushDelay)
    if (authStore.token) {
      void refreshRushDependents(vaultId, authStore.token, result.incident_id).catch((error) => {
        handleStoreError(error, 'Failed to refresh vault after rushing room')
      })
    }
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

  async function fetchGridConfig(token: string): Promise<void> {
    try {
      const response = await axios.get<GridConfig>('/api/v1/rooms/grid-config/', {
        headers: { Authorization: `Bearer ${token}` },
      })
      gridConfig.value = response.data
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
