import { describe, expect, it, beforeEach } from 'vitest'
import {
  addPendingReport,
  removePendingReport,
  usePendingReports,
} from '@/modules/exploration/composables/usePendingReports'

const rewards = {
  caps: 25,
  items: [],
  experience: 10,
  distance: 5,
  enemies_defeated: 0,
  events_encountered: 1,
}

describe('usePendingReports', () => {
  beforeEach(() => {
    for (const report of usePendingReports().pendingReports.value) removePendingReport(report.id)
  })

  it('keeps identical rewards from separate explorations and filters reports by vault', () => {
    addPendingReport({
      explorationId: 'exploration-1',
      vaultId: 'vault-1',
      dwellerId: 'dweller-1',
      dwellerName: 'Amata',
      rewards,
    })
    addPendingReport({
      explorationId: 'exploration-2',
      vaultId: 'vault-2',
      dwellerId: 'dweller-1',
      dwellerName: 'Amata',
      rewards,
    })

    expect(usePendingReports().pendingReports.value).toHaveLength(2)
    expect(usePendingReports('vault-1').pendingReports.value).toHaveLength(1)
    expect(usePendingReports('vault-2').pendingReports.value).toHaveLength(1)
  })

  it('deduplicates a report received through both SSE and notification delivery', () => {
    const report = {
      explorationId: 'exploration-1',
      vaultId: 'vault-1',
      dwellerId: 'dweller-1',
      dwellerName: 'Amata',
      rewards,
    }

    addPendingReport(report)
    addPendingReport(report)

    expect(usePendingReports().pendingReports.value).toHaveLength(1)
  })
})
