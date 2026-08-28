import { useStorage } from '@vueuse/core'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import type { RewardsSummary } from '../stores/exploration'

const STORAGE_KEY = 'vault.pendingExplorationReports'

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

export function addPendingReport(report: Omit<PendingExplorationReport, 'id' | 'createdAt'>): void {
  if (pendingReports.value.some((existing) => existing.explorationId === report.explorationId)) return
  pendingReports.value = [
    ...pendingReports.value,
    { ...report, id: report.explorationId, createdAt: new Date().toISOString() },
  ]
}

export function removePendingReport(reportId: string): void {
  pendingReports.value = pendingReports.value.filter((r) => r.id !== reportId)
}

export function usePendingReports(vaultId?: MaybeRefOrGetter<string | undefined>) {
  const reports = vaultId
    ? computed(() => pendingReports.value.filter((report) => report.vaultId === toValue(vaultId)))
    : pendingReports
  return { pendingReports: reports }
}
