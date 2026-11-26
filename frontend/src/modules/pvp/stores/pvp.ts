import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { handleStoreError } from '@/core/utils/errorHandler'
import { pvpDuelService, type PvpBoardEntry, type PvpDuel } from '../services/pvpDuelService'

export const usePvpStore = defineStore('pvp', () => {
  const authStore = useAuthStore()
  const board = ref<PvpBoardEntry[]>([])
  const ownOpenDuel = ref<PvpDuel | null>(null)
  const displayedDuel = ref<PvpDuel | null>(null)
  // Which vault the state above actually belongs to. A passive reader (the vault banner) must not
  // show one vault's board under another vault's heading, so it compares this against its own id.
  const stateVaultId = ref<string | null>(null)
  const loading = ref(false)
  const acting = ref(false)
  const hasOpenChallenge = computed(() => ownOpenDuel.value?.status === 'OPEN')
  let loadVersion = 0
  let operationVersion = 0

  function clear(): void {
    board.value = []
    ownOpenDuel.value = null
    displayedDuel.value = null
    stateVaultId.value = null
  }

  async function load(
    vaultId: string,
    requestedDuel?: string,
    options: { silent?: boolean } = {}
  ): Promise<boolean> {
    const version = ++loadVersion
    // Capture the session: a load that started before a logout must never commit afterwards, or
    // the next account would inherit the previous one's challenge.
    const session = authStore.sessionGeneration
    operationVersion++
    acting.value = false
    loading.value = true
    // Switching vaults must not leave the previous vault's challenge on screen while this loads.
    if (stateVaultId.value !== vaultId) clear()
    try {
      const [entries, current] = await Promise.all([
        pvpDuelService.list(vaultId),
        pvpDuelService.current(vaultId),
      ])
      if (version !== loadVersion || session !== authStore.sessionGeneration) return false
      const displayed = requestedDuel ? await pvpDuelService.get(vaultId, requestedDuel) : current
      if (version !== loadVersion || session !== authStore.sessionGeneration) return false
      board.value = entries
      ownOpenDuel.value = current
      displayedDuel.value = displayed
      stateVaultId.value = vaultId
      return true
    } catch (error) {
      // A passive caller (the vault banner) passes ``silent``: a failed background load must not
      // raise a toast in front of a player who never asked for the board.
      if (version === loadVersion && session === authStore.sessionGeneration)
        handleStoreError(error, 'Failed to load the raid board', !options.silent)
      return false
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }

  async function post(vaultId: string, dwellerIds: string[]): Promise<PvpDuel | null> {
    const version = loadVersion
    const operation = ++operationVersion
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
      if (operation === operationVersion) acting.value = false
    }
  }

  async function accept(
    vaultId: string,
    duelId: string,
    dwellerIds: string[]
  ): Promise<PvpDuel | null> {
    const version = loadVersion
    const operation = ++operationVersion
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
      if (operation === operationVersion) acting.value = false
    }
  }

  return {
    board,
    ownOpenDuel,
    displayedDuel,
    stateVaultId,
    loading,
    acting,
    hasOpenChallenge,
    clear,
    load,
    post,
    accept,
  }
})
