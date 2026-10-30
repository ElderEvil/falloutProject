import { useStorage } from '@vueuse/core'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { RewardsSummary } from '../stores/exploration'

const STORAGE_KEY = 'vault.pendingExplorationReports'
const ACKNOWLEDGED_KEY = 'vault.acknowledgedExplorationReports'
const MAX_ACKNOWLEDGED_REPORTS = 200

export interface PendingExplorationReport {
  id: string
  explorationId: string
  vaultId: string
  dwellerId: string
  dwellerName: string
  rewards: RewardsSummary
  createdAt: string
}

const pendingReports = useStorage<PendingExplorationReport[]>(STORAGE_KEY, [])
const acknowledgedReportIds = useStorage<string[]>(ACKNOWLEDGED_KEY, [])

export function isReportAcknowledged(explorationId: string): boolean {
  return acknowledgedReportIds.value.includes(explorationId)
}

export function addPendingReport(report: Omit<PendingExplorationReport, 'id' | 'createdAt'>): void {
  if (!report.explorationId || isReportAcknowledged(report.explorationId)) return
  if (pendingReports.value.some((existing) => existing.explorationId === report.explorationId))
    return
  pendingReports.value = [
    ...pendingReports.value,
    { ...report, id: report.explorationId, createdAt: new Date().toISOString() },
  ]
}

export function removePendingReport(reportId: string): void {
  pendingReports.value = pendingReports.value.filter((r) => r.id !== reportId)
}

/** Drop the queued report and remember it, so a replayed SSE frame or an old bell row cannot resurrect it. */
export function acknowledgeReport(explorationId: string): void {
  if (!explorationId) return
  removePendingReport(explorationId)
  if (isReportAcknowledged(explorationId)) return
  acknowledgedReportIds.value = [...acknowledgedReportIds.value, explorationId].slice(
    -MAX_ACKNOWLEDGED_REPORTS
  )
}

export function usePendingReports(vaultId?: MaybeRefOrGetter<string | undefined>) {
  const reports = vaultId
    ? computed(() => pendingReports.value.filter((report) => report.vaultId === toValue(vaultId)))
    : pendingReports
  return { pendingReports: reports }
}
