import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { handleStoreError } from '@/core/utils/errorHandler'
import { pvpDuelService, type PvpBoardEntry, type PvpDuel } from '../services/pvpDuelService'

export const usePvpStore = defineStore('pvp', () => {
  const board = ref<PvpBoardEntry[]>([])
  const ownOpenDuel = ref<PvpDuel | null>(null)
  const displayedDuel = ref<PvpDuel | null>(null)
  const loading = ref(false)
  const acting = ref(false)
  const hasOpenChallenge = computed(() => ownOpenDuel.value?.status === 'OPEN')
  let loadVersion = 0

  async function load(vaultId: string, requestedDuel?: string): Promise<boolean> {
    const version = ++loadVersion
    loading.value = true
    try {
      const [entries, current] = await Promise.all([
        pvpDuelService.list(vaultId),
        pvpDuelService.current(vaultId),
      ])
      if (version !== loadVersion) return false
      const displayed = requestedDuel ? await pvpDuelService.get(vaultId, requestedDuel) : current
      if (version !== loadVersion) return false
      board.value = entries
      ownOpenDuel.value = current
      displayedDuel.value = displayed
      return true
    } catch (error) {
      if (version === loadVersion) handleStoreError(error, 'Failed to load The Pit')
      return false
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }

  async function post(vaultId: string, dwellerIds: string[]): Promise<PvpDuel | null> {
    const version = loadVersion
    acting.value = true
    try {
      const duel = await pvpDuelService.post(vaultId, dwellerIds)
      if (version !== loadVersion) return null
      ownOpenDuel.value = duel
      displayedDuel.value = duel
      return duel
    } catch (error) {
      if (version === loadVersion) handleStoreError(error, 'Failed to post the challenge')
      return null
    } finally {
      if (version === loadVersion) acting.value = false
    }
  }

  async function accept(
    vaultId: string,
    duelId: string,
    dwellerIds: string[]
  ): Promise<PvpDuel | null> {
    const version = loadVersion
    acting.value = true
    try {
      const duel = await pvpDuelService.accept(vaultId, duelId, dwellerIds)
      if (version !== loadVersion) return null
      displayedDuel.value = duel
      board.value = board.value.filter((entry) => entry.duel_id !== duelId)
      return duel
    } catch (error) {
      if (version === loadVersion) handleStoreError(error, 'Failed to accept the challenge')
      return null
    } finally {
      if (version === loadVersion) acting.value = false
    }
  }

  return {
    board,
    ownOpenDuel,
    displayedDuel,
    loading,
    acting,
    hasOpenChallenge,
    load,
    post,
    accept,
  }
})
