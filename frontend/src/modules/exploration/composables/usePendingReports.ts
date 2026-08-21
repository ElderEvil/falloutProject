import { useStorage } from '@vueuse/core'
import type { RewardsSummary } from '../stores/exploration'

const STORAGE_KEY = 'vault.pendingExplorationReports'

export interface PendingExplorationReport {
  id: string
  vaultId: string
  dwellerId: string
  dwellerName: string
  rewards: RewardsSummary
  createdAt: string
}

/**
 * Durable, offline-safe queue of completed exploration reward reports that
 * have not yet been acknowledged by the Overseer.
 *
 * Exploration completions that happen while the player is elsewhere (or while
 * the app is closed) must not be lost — the reward screen has to be visible at
 * least once. Reports are persisted to localStorage via `useStorage` (survive
 * reload/offline) and surfaced on the next visit to the exploration view, one
 * at a time, and removed only when the player acknowledges the modal.
 *
 * The module-scoped ref is the single shared in-memory queue, so the
 * notification bell and the exploration view always read the same state.
 */
const pendingReports = useStorage<PendingExplorationReport[]>(STORAGE_KEY, [])

/**
 * Add a report to the pending queue. Deduplicates by dweller + rewards content
 * so the same completion enqueued both by the notification bell and the SSE
 * stream is stored once, while a later distinct completion is kept.
 */
export function addPendingReport(report: Omit<PendingExplorationReport, 'id' | 'createdAt'>): void {
  const rewardsSignature = JSON.stringify(report.rewards)
  if (
    pendingReports.value.some(
      (r) => r.dwellerId === report.dwellerId && JSON.stringify(r.rewards) === rewardsSignature
    )
  ) {
    return
  }
  pendingReports.value = [
    ...pendingReports.value,
    { ...report, id: `${report.dwellerId}-${Date.now()}`, createdAt: new Date().toISOString() },
  ]
}

/** Remove a specific report once it has been acknowledged. */
export function removePendingReport(reportId: string): void {
  pendingReports.value = pendingReports.value.filter((r) => r.id !== reportId)
}

/** Reactive read access to the shared pending queue. */
export function usePendingReports(): { pendingReports: typeof pendingReports } {
  return { pendingReports }
}
