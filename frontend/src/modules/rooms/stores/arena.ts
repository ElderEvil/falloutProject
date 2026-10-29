import { defineStore } from 'pinia'
import { ref } from 'vue'
import { arenaApi } from '../api/arena'
import type { ArenaCreature, ArenaFighterSelection, ArenaRoomState } from '../api/arena'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useArenaStore = defineStore('arena', () => {
  const rooms = ref<Map<string, ArenaRoomState>>(new Map())
  const creatures = ref<ArenaCreature[]>([])
  let stateRequest = 0
  let contextEpoch = 0
  let activeVaultId: string | null = null

  async function fetchState(vaultId: string, silent = false): Promise<boolean> {
    if (activeVaultId !== vaultId) {
      contextEpoch += 1
      activeVaultId = vaultId
    }
    const request = ++stateRequest
    const epoch = contextEpoch
    try {
      const state = await arenaApi.fetchState(vaultId)
      // Same-vault polling supersedes state delivery without rejecting a successful mutation.
      if (request !== stateRequest) return epoch === contextEpoch
      rooms.value = new Map(state.rooms.map((room) => [room.room_id, room]))
      return true
    } catch (error) {
      if (!silent) handleStoreError(error, 'Failed to load arena state')
      return false
    }
  }

  async function fetchCreatures(vaultId: string): Promise<boolean> {
    try {
      creatures.value = await arenaApi.fetchCreatures(vaultId)
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to load hunt creatures')
      return false
    }
  }

  async function setFighters(
    vaultId: string,
    roomId: string,
    selection: ArenaFighterSelection
  ): Promise<boolean> {
    try {
      await arenaApi.setFighters(vaultId, roomId, selection)
      return await fetchState(vaultId, true)
    } catch (error) {
      handleStoreError(error, 'Failed to update fighters')
      return false
    }
  }

  async function startFight(
    vaultId: string,
    roomId: string,
    selection?: ArenaFighterSelection
  ): Promise<boolean> {
    const epoch = contextEpoch
    try {
      await arenaApi.startFight(vaultId, roomId, selection)
      if (epoch !== contextEpoch) return false
      return await fetchState(vaultId, true)
    } catch (error) {
      handleStoreError(error, 'Failed to start fight')
      return false
    }
  }

  async function stopFight(vaultId: string, roomId: string): Promise<boolean> {
    try {
      await arenaApi.stopFight(vaultId, roomId)
      return await fetchState(vaultId, true)
    } catch (error) {
      handleStoreError(error, 'Failed to stop fight')
      return false
    }
  }

  async function queueSkill(vaultId: string, roomId: string, fighterId: string): Promise<boolean> {
    try {
      await arenaApi.queueSkill(vaultId, roomId, fighterId)
      return await fetchState(vaultId, true)
    } catch (error) {
      handleStoreError(error, 'Failed to use active skill')
      return false
    }
  }

  async function clearEvents(vaultId: string, roomId: string): Promise<boolean> {
    try {
      await arenaApi.clearEvents(vaultId, roomId)
      return await fetchState(vaultId, true)
    } catch (error) {
      handleStoreError(error, 'Failed to clear the battle journal')
      return false
    }
  }

  function getRoom(roomId: string): ArenaRoomState | null {
    return rooms.value.get(roomId) ?? null
  }

  function reset(): void {
    stateRequest += 1
    contextEpoch += 1
    activeVaultId = null
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
    stopFight,
    queueSkill,
    clearEvents,
    getRoom,
    reset,
  }
})
