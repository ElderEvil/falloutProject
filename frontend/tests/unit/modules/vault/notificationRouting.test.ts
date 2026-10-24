import { describe, expect, it } from 'vite-plus/test'

import {
  getNotificationRoute,
  getNotificationSound,
  getNotificationAnimation,
} from '@/modules/vault/utils/notificationRouting'
const levelUpNotification = {
  vault_id: 'vault-1',
  from_dweller_id: 'dweller-1',
  notification_type: 'level_up',
}

describe('getNotificationRoute', () => {
  it('opens the vault for a room unlock rather than a source dweller', () => {
    expect(
      getNotificationRoute({
        vault_id: 'vault-1',
        notification_type: 'room_unlocked',
        from_dweller_id: 'dweller-1',
      })
    ).toBe('/vault/vault-1')
  })

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

  it('routes a location_cleared notification to the map', () => {
    expect(
      getNotificationRoute({
        vault_id: 'vault-1',
        notification_type: 'location_cleared',
      })
    ).toBe('/vault/vault-1/map')
  })

  it('routes a location_ready notification to the map with the place deep link', () => {
    expect(
      getNotificationRoute({
        vault_id: 'vault-1',
        notification_type: 'location_ready',
        meta_data: { location_id: 'loc-1' },
      })
    ).toBe('/vault/vault-1/map?place=loc-1')
  })
})

describe('getNotificationSound', () => {
  it('gives a distinct cue to each bell event that previously used the generic alert', () => {
    expect(getNotificationSound('crafting_complete')).toBe('craftComplete')
    expect(getNotificationSound('baby_born')).toBe('babyBorn')
    expect(getNotificationSound('power_outage')).toBe('powerOutage')
  })

  it('leaves combat on the generic alert so the incident stream does not double-play', () => {
    expect(getNotificationSound('combat_started')).toBe('notification')
    expect(getNotificationSound('combat_victory')).toBe('notification')
    expect(getNotificationSound('combat_defeat')).toBe('notification')
  })

  it('keeps the cues that were already wired', () => {
    expect(getNotificationSound('level_up')).toBe('levelUp')
    expect(getNotificationSound('training_complete')).toBe('trainingComplete')
    expect(getNotificationSound('radio_new_dweller')).toBe('radioRecruit')
    expect(getNotificationSound('objective_completed')).toBe('objectiveReady')
  })

  it('falls back to the generic alert for an unknown notification type', () => {
    expect(getNotificationSound('something_new')).toBe('notification')
  })
})

it.each([
  ['storage_item_degraded', 'resourceLow'],
  ['storage_item_upgraded', 'craftComplete'],
])('routes %s to storage', (notification_type, sound) => {
  expect(getNotificationRoute({ vault_id: 'vault-1', notification_type })).toBe(
    '/vault/vault-1/storage'
  )
  expect(getNotificationSound(notification_type)).toBe(sound)
})
it.each([
  ['baby_born', 'baby'],
  ['training_complete', 'ok'],
  ['objective_completed', 'ok'],
  ['achievement_unlocked', 'ok'],
  ['room_unlocked', 'ok'],
  ['quest_complete', 'ok'],
  ['combat_victory', 'ok'],
  ['level_up', 'ok'],
  ['resource_low', null],
  ['rush_failed', null],
  ['unknown', null],
])('maps %s to a suitable notification animation', (type, expected) => {
  expect(getNotificationAnimation(type)).toBe(expected)
})

describe('rush notifications', () => {
  it.each(['rush_succeeded', 'rush_failed'])(
    'routes %s to the rushed room',
    (notification_type) => {
      expect(
        getNotificationRoute({
          vault_id: 'vault-1',
          notification_type,
          meta_data: { room_id: 'room-1' },
        })
      ).toBe('/vault/vault-1?roomId=room-1')
    }
  )

  it('falls back to the vault when the room id is missing', () => {
    expect(getNotificationRoute({ vault_id: 'vault-1', notification_type: 'rush_succeeded' })).toBe(
      '/vault/vault-1'
    )
  })

  it('gives each outcome a dedicated cue', () => {
    expect(getNotificationSound('rush_succeeded')).toBe('rushSuccess')
    expect(getNotificationSound('rush_failed')).toBe('rushFail')
  })
})
})
