import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useIntervalFn } from '@vueuse/core'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import * as combatZoneService from '../api/combatZoneService'
import type {
  CombatZoneLobbyRead,
  CombatZoneMatchRead,
  CombatZonePartyRead,
  CombatZoneStance,
} from '../models/combatZone'

export const useCombatZoneStore = defineStore('combatZone', () => {
  const lobby = ref<CombatZoneLobbyRead | null>(null)
  const party = ref<CombatZonePartyRead | null>(null)
  const match = ref<CombatZoneMatchRead | null>(null)
  const activeMatchId = ref<string | null>(null)
  const isLoading = ref(false)
  const isRefreshing = ref(false)
  const isMatchLoading = ref(false)
  const error = ref<string | null>(null)

  let _vaultId: string | null = null
  let _token: string | null = null

  const toast = useToast()
  const isMatchFinished = computed(() => match.value?.status === 'finished')

  const { pause: pauseLobby, resume: resumeLobby } = useIntervalFn(() => void refresh(), 5000, {
    immediate: false,
  })

  const { pause: pauseMatch, resume: resumeMatch } = useIntervalFn(
    () => void refreshMatch(),
    2000,
    { immediate: false }
  )

  function canCall(): boolean {
    return Boolean(_vaultId && _token)
  }

  async function refresh(): Promise<void> {
    if (!canCall() || !_token || !_vaultId) return
    isRefreshing.value = true
    error.value = null
    try {
      const [nextLobby, nextParty] = await Promise.all([
        combatZoneService.getLobby(_token),
        combatZoneService.getParty(_token, _vaultId),
      ])
      lobby.value = nextLobby
      party.value = nextParty
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to load the Combat Zone')
    } finally {
      isRefreshing.value = false
    }
  }

  async function open(vaultId: string, token: string): Promise<void> {
    _vaultId = vaultId
    _token = token
    match.value = null
    activeMatchId.value = null
    pauseMatch()
    await refresh()
    resumeLobby()
  }

  function close(): void {
    pauseLobby()
    pauseMatch()
    _vaultId = null
    _token = null
    lobby.value = null
    party.value = null
    match.value = null
    activeMatchId.value = null
    error.value = null
  }

  async function sendParty(dwellerId: string): Promise<boolean> {
    if (!_token || !_vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      party.value = await combatZoneService.sendParty(_token, _vaultId, dwellerId)
      toast.success('Contender dispatched to Interchange 77')
      await refresh()
      return true
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to send a contender')
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function recallParty(): Promise<boolean> {
    if (!_token || !_vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      party.value = await combatZoneService.recallParty(_token, _vaultId)
      toast.success('Contender recalled')
      await refresh()
      return true
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to recall the contender')
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function setStance(stance: CombatZoneStance): Promise<void> {
    if (!_token || !_vaultId) return
    error.value = null
    try {
      party.value = await combatZoneService.setStance(_token, _vaultId, stance)
      if (activeMatchId.value) await refreshMatch()
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to set the stance')
    }
  }

  async function challenge(targetPartyId: string): Promise<boolean> {
    if (!_token || !_vaultId) return false
    isLoading.value = true
    error.value = null
    try {
      const nextMatch = await combatZoneService.challenge(_token, _vaultId, targetPartyId)
      match.value = nextMatch
      activeMatchId.value = nextMatch.id
      resumeMatch()
      return true
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to challenge that party')
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function watchMatch(matchId: string): Promise<void> {
    activeMatchId.value = matchId
    await refreshMatch()
    resumeMatch()
  }

  async function refreshMatch(): Promise<void> {
    if (!_token || !activeMatchId.value) return
    isMatchLoading.value = true
    try {
      match.value = await combatZoneService.getMatch(_token, activeMatchId.value)
      if (match.value.status === 'finished') pauseMatch()
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to load the bout')
    } finally {
      isMatchLoading.value = false
    }
  }

  async function setVaultEnabled(
    vaultId: string,
    token: string,
    enabled: boolean
  ): Promise<boolean> {
    try {
      const result = await combatZoneService.setVaultEnabled(token, vaultId, enabled)
      toast.success(
        result.enabled
          ? 'Combat Zone enabled for this vault'
          : 'Combat Zone disabled for this vault'
      )
      return result.enabled === enabled
    } catch (err) {
      error.value = handleStoreError(err, 'Failed to update the Combat Zone switch')
      return false
    }
  }

  function backToLobby(): void {
    pauseMatch()
    activeMatchId.value = null
    match.value = null
    void refresh()
  }

  return {
    lobby,
    party,
    match,
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
    setVaultEnabled,
    watchMatch,
    refreshMatch,
    backToLobby,
  }
})
