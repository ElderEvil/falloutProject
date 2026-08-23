import { defineStore } from 'pinia'
import { ref } from 'vue'
import { arenaApi } from '../api/arena'
import type { ArenaRoomState } from '../api/arena'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useArenaStore = defineStore('arena', () => {
  const rooms = ref<Map<string, ArenaRoomState>>(new Map())

  async function fetchState(vaultId: string, token: string, silent = false): Promise<boolean> {
    try {
      const state = await arenaApi.fetchState(vaultId, token)
      rooms.value = new Map(state.rooms.map((room) => [room.room_id, room]))
      return true
    } catch (error) {
      if (!silent) handleStoreError(error, 'Failed to load arena state')
      return false
    }
  }

  async function setFighters(
    vaultId: string,
    roomId: string,
    fighterAId: string | null,
    fighterBId: string | null,
    token: string
  ): Promise<boolean> {
    try {
      await arenaApi.setFighters(vaultId, roomId, fighterAId, fighterBId, token)
      return await fetchState(vaultId, token, true)
    } catch (error) {
      handleStoreError(error, 'Failed to update fighters')
      return false
    }
  }

  async function startFight(vaultId: string, roomId: string, token: string): Promise<boolean> {
    try {
      await arenaApi.startFight(vaultId, roomId, token)
      return await fetchState(vaultId, token, true)
    } catch (error) {
      handleStoreError(error, 'Failed to start fight')
      return false
    }
  }

  async function clearEvents(vaultId: string, roomId: string, token: string): Promise<boolean> {
    try {
      await arenaApi.clearEvents(vaultId, roomId, token)
      return await fetchState(vaultId, token, true)
    } catch (error) {
      handleStoreError(error, 'Failed to clear the battle journal')
      return false
    }
  }

  function getRoom(roomId: string): ArenaRoomState | null {
    return rooms.value.get(roomId) ?? null
  }

  function reset(): void {
    rooms.value = new Map()
  }

  return {
    rooms,
    fetchState,
    setFighters,
    startFight,
    clearEvents,
    getRoom,
    reset,
  }
})
