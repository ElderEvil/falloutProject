import { describe, expect, it } from 'vitest'
import { getNotificationRoute } from '@/modules/vault/utils/notificationRouting'

const levelUpNotification = {
  vault_id: 'vault-1',
  from_dweller_id: 'dweller-1',
  notification_type: 'level_up',
}

describe('getNotificationRoute', () => {
  it('opens the source dweller for a level-up notification', () => {
    expect(getNotificationRoute(levelUpNotification)).toBe('/vault/vault-1/dwellers/dweller-1')
  })

  it('opens the returned quest reward modal', () => {
    expect(
      getNotificationRoute({
        vault_id: 'vault-1',
        notification_type: 'quest_complete',
        meta_data: { quest_id: 'quest-1', ready_to_claim: true },
      })
    ).toBe('/vault/vault-1/quests?claimQuest=quest-1')
  })

  it('keeps other quest notifications on the quest list', () => {
    expect(
      getNotificationRoute({
        vault_id: 'vault-1',
        notification_type: 'quest_complete',
        meta_data: { quest_id: 'quest-1', ready_to_claim: false },
      })
    ).toBe('/vault/vault-1/quests')
  })
})
