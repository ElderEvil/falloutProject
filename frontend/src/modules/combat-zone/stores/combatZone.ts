import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { usePolling } from '@/core/composables/usePolling'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import * as combatZoneService from '../api/combatZoneService'
import type {
  CombatZoneHistoryEntry,
  CombatZoneLobbyRead,
  CombatZoneMatchRead,
  CombatZonePartyRead,
  CombatZoneStance,
} from '../models/combatZone'

export const useCombatZoneStore = defineStore('combatZone', () => {
  const lobby = ref<CombatZoneLobbyRead | null>(null)
  const party = ref<CombatZonePartyRead | null>(null)
  const match = ref<CombatZoneMatchRead | null>(null)
  const history = ref<CombatZoneHistoryEntry[]>([])
  const activeMatchId = ref<string | null>(null)
  const isLoading = ref(false)
  const isRefreshing = ref(false)
  const isMatchLoading = ref(false)
  const error = ref<string | null>(null)

  let _vaultId: string | null = null
  let _token: string | null = null
  let _generation = 0
  let _refreshRequest = 0
  let _matchRequest = 0

  const toast = useToast()
  const isMatchFinished = computed(() => match.value?.status === 'finished')

  const lobbyPoll = usePolling(refresh, { interval: 5000, immediate: false })
  const matchPoll = usePolling(refreshMatch, { interval: 2000, immediate: false })

  function invalidateRefresh(): void {
    _refreshRequest++
    isRefreshing.value = false
  }

  async function refresh(): Promise<void> {
    const request = ++_refreshRequest
    const generation = _generation
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return
    isRefreshing.value = true
    error.value = null
    try {
      const [nextLobby, nextParty] = await Promise.all([
        combatZoneService.getLobby(token),
        combatZoneService.getParty(token, vaultId),
      ])
      if (
        request !== _refreshRequest ||
        generation !== _generation ||
        _token !== token ||
        _vaultId !== vaultId
      )
        return
      lobby.value = nextLobby
      party.value = nextParty
    } catch (err) {
      if (request === _refreshRequest && generation === _generation) {
        error.value = handleStoreError(err, 'Failed to load the Combat Zone')
      }
    } finally {
      if (request === _refreshRequest) isRefreshing.value = false
    }
  }

  async function open(vaultId: string, token: string): Promise<void> {
    const sameVault = _vaultId === vaultId
    const generation = ++_generation
    invalidateRefresh()
    if (!sameVault) {
      lobby.value = null
      party.value = null
      history.value = []
      error.value = null
      match.value = null
      activeMatchId.value = null
    }
    _vaultId = vaultId
    _token = token
    lobbyPoll.pause()
    matchPoll.pause()
    await refresh()
    if (generation !== _generation) return
    await loadHistory()
    if (generation !== _generation) return
    lobbyPoll.resume()
    if (activeMatchId.value && match.value?.status !== 'finished') matchPoll.resume()
    else matchPoll.pause()
  }

  function close(): void {
    _generation++
    invalidateRefresh()
    _matchRequest++
    lobbyPoll.pause()
    matchPoll.pause()
    _vaultId = null
    _token = null
    lobby.value = null
    party.value = null
    match.value = null
    history.value = []
    activeMatchId.value = null
    error.value = null
  }

  async function sendParty(dwellerId: string): Promise<boolean> {
    const generation = _generation
    invalidateRefresh()
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      const nextParty = await combatZoneService.sendParty(token, vaultId, dwellerId)
      if (generation !== _generation || _token !== token || _vaultId !== vaultId) return false
      invalidateRefresh()
      party.value = nextParty
      toast.success('Contender dispatched to Interchange 77')
      await refresh()
      return true
    } catch (err) {
      if (generation === _generation) {
        error.value = handleStoreError(err, 'Failed to send a contender')
      }
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function recallParty(): Promise<boolean> {
    const generation = _generation
    invalidateRefresh()
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      const nextParty = await combatZoneService.recallParty(token, vaultId)
      if (generation !== _generation || _token !== token || _vaultId !== vaultId) return false
      invalidateRefresh()
      party.value = nextParty
      toast.success('Contender recalled')
      await refresh()
      return true
    } catch (err) {
      if (generation === _generation) {
        error.value = handleStoreError(err, 'Failed to recall the contender')
      }
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function setStance(stance: CombatZoneStance): Promise<void> {
    const generation = _generation
    invalidateRefresh()
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return
    error.value = null
    try {
      const nextParty = await combatZoneService.setStance(token, vaultId, stance)
      if (generation !== _generation || _token !== token || _vaultId !== vaultId) return
      invalidateRefresh()
      party.value = nextParty
      if (activeMatchId.value) await refreshMatch()
    } catch (err) {
      if (generation === _generation) {
        error.value = handleStoreError(err, 'Failed to set the stance')
      }
    }
  }

  async function challenge(targetPartyId: string): Promise<boolean> {
    const generation = _generation
    invalidateRefresh()
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      const nextMatch = await combatZoneService.challenge(token, vaultId, targetPartyId)
      if (generation !== _generation || _token !== token || _vaultId !== vaultId) return false
      invalidateRefresh()
      match.value = nextMatch
      activeMatchId.value = nextMatch.id
      matchPoll.resume()
      return true
    } catch (err) {
      if (generation === _generation) {
        error.value = handleStoreError(err, 'Failed to challenge that party')
      }
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function watchMatch(matchId: string): Promise<void> {
    const generation = _generation
    activeMatchId.value = matchId
    await refreshMatch()
    if (generation !== _generation || activeMatchId.value !== matchId) return
    if (match.value?.status === 'finished') matchPoll.pause()
    else matchPoll.resume()
  }

  async function refreshMatch(): Promise<void> {
    const request = ++_matchRequest
    const generation = _generation
    const token = _token
    const matchId = activeMatchId.value
    if (!token || !matchId) return
    isMatchLoading.value = true
    try {
      const previousStatus = match.value?.status
      const previousMatchId = match.value?.id
      const nextMatch = await combatZoneService.getMatch(token, matchId)
      if (
        request !== _matchRequest ||
        generation !== _generation ||
        activeMatchId.value !== matchId ||
        _token !== token
      )
        return
      if (match.value?.id === matchId) {
        if (match.value.status === 'finished' && nextMatch.status !== 'finished') return
        if (nextMatch.cursor.sequence < match.value.cursor.sequence) return
      }
      match.value = nextMatch
      if (nextMatch.status === 'finished') {
        matchPoll.pause()
        if (previousStatus !== 'finished' || previousMatchId !== matchId) await loadHistory()
      }
    } catch (err) {
      if (request === _matchRequest && generation === _generation) {
        error.value = handleStoreError(err, 'Failed to load the bout')
      }
    } finally {
      if (request === _matchRequest) isMatchLoading.value = false
    }
  }

  async function loadHistory(): Promise<void> {
    const generation = _generation
    const token = _token
    const vaultId = _vaultId
    if (!token || !vaultId) return
    try {
      const entries = await combatZoneService.getHistory(token, vaultId)
      if (generation !== _generation || _token !== token || _vaultId !== vaultId) return
      history.value = entries
    } catch (err) {
      if (generation === _generation) {
        error.value = handleStoreError(err, 'Failed to load Combat Zone history')
      }
    }
  }

  function backToLobby(): void {
    matchPoll.pause()
    activeMatchId.value = null
    match.value = null
    void refresh()
  }

  return {
    lobby,
    party,
    match,
    history,
    activeMatchId,
    isLoading,
    isRefreshing,
    isMatchLoading,
    error,
    isMatchFinished,
    open,
    close,
    refresh,
    sendParty,
    recallParty,
    setStance,
    challenge,
    loadHistory,
    watchMatch,
    refreshMatch,
    backToLobby,
  }
})
