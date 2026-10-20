import { defineStore } from 'pinia'
import { ref } from 'vue'
import { arenaApi } from '../api/arena'
import type { ArenaCreature, ArenaFighterSelection, ArenaRoomState } from '../api/arena'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useArenaStore = defineStore('arena', () => {
  const rooms = ref<Map<string, ArenaRoomState>>(new Map())
  const creatures = ref<ArenaCreature[]>([])

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

  async function fetchCreatures(vaultId: string, token: string): Promise<boolean> {
    try {
      creatures.value = await arenaApi.fetchCreatures(vaultId, token)
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to load hunt creatures')
      return false
    }
  }

  async function setFighters(
    vaultId: string,
    roomId: string,
    selection: ArenaFighterSelection,
    token: string
  ): Promise<boolean> {
    try {
      await arenaApi.setFighters(vaultId, roomId, selection, token)
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

  async function queueSkill(
    vaultId: string,
    roomId: string,
    fighterId: string,
    token: string
  ): Promise<boolean> {
    try {
      await arenaApi.queueSkill(vaultId, roomId, fighterId, token)
      return await fetchState(vaultId, token, true)
    } catch (error) {
      handleStoreError(error, 'Failed to use active skill')
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
    creatures.value = []
  }

  return {
    rooms,
    creatures,
    fetchState,
    fetchCreatures,
    setFighters,
    startFight,
    queueSkill,
    clearEvents,
    getRoom,
    reset,
  }
})
