import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { usePolling } from '@/core/composables/usePolling'
import { handleStoreError } from '@/core/utils/errorHandler'
import type { EnvoyConfig, EnvoyFiling, EnvoySignal } from '../models/envoy'
import { envoyService } from '../services/envoyService'

/** One band sweep every 30 s; the store is the only poll owner for the terminal. */
const POLL_INTERVAL_MS = 30_000

/** incoming hails first, then reachable vaults by distance, then the rest by distance. */
function rank(signal: EnvoySignal): number {
  if (signal.incoming_hail) return 0
  return signal.can_hail ? 1 : 2
}

function compareSignals(first: EnvoySignal, second: EnvoySignal): number {
  const byRank = rank(first) - rank(second)
  if (byRank !== 0) return byRank
  const firstDistance = first.distance ?? Number.POSITIVE_INFINITY
  const secondDistance = second.distance ?? Number.POSITIVE_INFINITY
  if (firstDistance !== secondDistance) return firstDistance - secondDistance
  return first.number - second.number
}

export const useEnvoyStore = defineStore('envoy', () => {
  const signals = ref<EnvoySignal[]>([])
  const filings = ref<EnvoyFiling[]>([])
  const config = ref<EnvoyConfig | null>(null)
  const loading = ref(false)
  const refreshing = ref(false)
  const acting = ref(false)
  const errorMessage = ref<string | null>(null)
  const actionError = ref<string | null>(null)
  /** Vault the state above belongs to; guards delayed reads after a switch. */
  const stateVaultId = ref<string | null>(null)
  let loadVersion = 0
  /** Bumped by every committed hail/answer; a sweep that started earlier loses. */
  let logRevision = 0
  /** Bumped by stop(); a start() still awaiting its first load must not poll again. */
  let lifecycle = 0
  /** Set when a sweep is asked for while another one runs; drained in its finally. */
  let sweepQueued = false

  const sortedSignals = computed(() => [...signals.value].sort(compareSignals))

  const pendingIncoming = computed(() =>
    filings.value.filter((filing) => filing.incoming && filing.status === 'PENDING')
  )

  const pendingIncomingCount = computed(() => pendingIncoming.value.length)

  const awaitingTargets = computed(
    () =>
      new Set(
        filings.value
          .filter(
            (filing) => !filing.incoming && filing.kind === 'HAIL' && filing.status === 'PENDING'
          )
          .map((filing) => filing.to_vault_id)
      )
  )

  const vaultNumbers = computed(() => {
    const numbers: Record<string, number> = {}
    for (const signal of signals.value) numbers[signal.vault_id] = signal.number
    return numbers
  })

  function vaultLabel(vaultId: string): string {
    const number = vaultNumbers.value[vaultId]
    return number ? `VAULT ${number}` : `VAULT ${vaultId.slice(0, 8).toUpperCase()}`
  }

  function pendingFilingFrom(vaultId: string): EnvoyFiling | null {
    return (
      filings.value.find(
        (filing) =>
          filing.incoming &&
          filing.status === 'PENDING' &&
          filing.kind === 'HAIL' &&
          filing.from_vault_id === vaultId
      ) ?? null
    )
  }

  function counterpartyOf(filing: EnvoyFiling): string {
    return filing.incoming ? filing.from_vault_id : filing.to_vault_id
  }

  function clear(): void {
    signals.value = []
    filings.value = []
    config.value = null
    errorMessage.value = null
    actionError.value = null
    stateVaultId.value = null
  }

  function clearActionError(): void {
    actionError.value = null
  }

  async function load(vaultId: string): Promise<boolean> {
    const version = ++loadVersion
    // The previous action's guard is now stale, so only this reset can clear it.
    acting.value = false
    sweepQueued = false
    loading.value = true
    errorMessage.value = null
    actionError.value = null
    if (stateVaultId.value !== vaultId) clear()
    try {
      const [nextSignals, nextFilings, nextConfig] = await Promise.all([
        envoyService.signals(vaultId),
        envoyService.log(vaultId),
        envoyService.config(vaultId),
      ])
      if (version !== loadVersion) return false
      signals.value = nextSignals
      filings.value = nextFilings
      config.value = nextConfig
      stateVaultId.value = vaultId
      return true
    } catch (error) {
      if (version === loadVersion)
        errorMessage.value = handleStoreError(error, 'Failed to load the Envoy Terminal', false)
      return false
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }

  /** Poll sweep: roster and log only; the knobs do not move between deploys. */
  async function refresh(): Promise<void> {
    const vaultId = stateVaultId.value
    if (!vaultId) return
    // A sweep already running would drop this call's read, so queue one instead of losing it.
    if (refreshing.value || loading.value) {
      sweepQueued = true
      return
    }
    const version = loadVersion
    const revision = logRevision
    refreshing.value = true
    try {
      const [nextSignals, nextFilings] = await Promise.all([
        envoyService.signals(vaultId),
        envoyService.log(vaultId),
      ])
      if (version !== loadVersion || revision !== logRevision) return
      signals.value = nextSignals
      filings.value = nextFilings
      errorMessage.value = null
    } catch (error) {
      // Keep the last good sweep on screen; the banner names the failure.
      if (version === loadVersion)
        errorMessage.value = handleStoreError(error, 'Failed to refresh the Envoy Terminal', false)
    } finally {
      refreshing.value = false
      if (sweepQueued) {
        sweepQueued = false
        void refresh()
      }
    }
  }

  async function hail(targetVaultId: string): Promise<boolean> {
    const vaultId = stateVaultId.value
    if (!vaultId || acting.value) return false
    const version = loadVersion
    acting.value = true
    actionError.value = null
    try {
      const filing = await envoyService.hail(vaultId, targetVaultId)
      if (version !== loadVersion) return false
      logRevision += 1
      filings.value = [
        filing,
        ...filings.value.filter((existing) => existing.filing_id !== filing.filing_id),
      ]
      return true
    } catch (error) {
      if (version === loadVersion)
        actionError.value = handleStoreError(error, 'Failed to transmit the hail', false)
      return false
    } finally {
      if (version === loadVersion) acting.value = false
    }
  }

  async function respond(filingId: string, accept: boolean): Promise<boolean> {
    const vaultId = stateVaultId.value
    if (!vaultId || acting.value) return false
    const version = loadVersion
    acting.value = true
    actionError.value = null
    try {
      const answered = await envoyService.respond(vaultId, filingId, accept)
      if (version !== loadVersion) return false
      logRevision += 1
      filings.value = filings.value.map((filing) =>
        filing.filing_id === answered.filing_id ? answered : filing
      )
      // Accepting opens a relation, refusing locks it: the roster owns both flags.
      await refresh()
      // The re-sweep outlives the answer: a switch during it makes the toast a lie.
      return version === loadVersion
    } catch (error) {
      if (version === loadVersion)
        actionError.value = handleStoreError(error, 'Failed to answer the filing', false)
      return false
    } finally {
      if (version === loadVersion) acting.value = false
    }
  }

  const { pause: pausePolling, resume: resumePolling } = usePolling(refresh, {
    interval: POLL_INTERVAL_MS,
    immediate: false,
  })
  pausePolling()

  async function start(vaultId: string): Promise<void> {
    const token = ++lifecycle
    await (stateVaultId.value === vaultId ? refresh() : load(vaultId))
    // stop() ran while that first load was in flight: an unmounted view stays silent.
    if (token !== lifecycle) return
    resumePolling()
  }

  function stop(): void {
    lifecycle += 1
    pausePolling()
  }

  /**
   * The session ended: the next account must never see this book.
   * Both version bumps strand any in-flight load/sweep/action on its guard.
   */
  function clearSession(): void {
    loadVersion += 1
    logRevision += 1
    stop()
    sweepQueued = false
    acting.value = false
    loading.value = false
    refreshing.value = false
    clear()
  }

  return {
    signals,
    filings,
    config,
    loading,
    refreshing,
    acting,
    errorMessage,
    actionError,
    stateVaultId,
    sortedSignals,
    pendingIncoming,
    pendingIncomingCount,
    awaitingTargets,
    vaultNumbers,
    vaultLabel,
    counterpartyOf,
    pendingFilingFrom,
    clear,
    clearActionError,
    load,
    refresh,
    hail,
    respond,
    start,
    stop,
    clearSession,
  }
})
