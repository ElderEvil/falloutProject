import { describe, expect, it } from 'vite-plus/test'

import {
  getNotificationRoute,
  getNotificationSound,
  getNotificationAnimation,
} from '@/modules/vault/utils/notificationRouting'

const route = (payload: Record<string, unknown>) =>
  getNotificationRoute({ vault_id: 'vault-1', ...payload } as never)

describe('getNotificationRoute', () => {
  it.each([
    [
      'the reported journey site, preserving the older update fallback',
      {
        notification_type: 'exploration_update',
        meta_data: { event: 'site_found', exploration_id: 'exp-1', site_id: 'red_rocket' },
      },
      '/vault/vault-1/exploration/exp-1?siteId=red_rocket',
    ],
    [
      'a bare exploration update',
      { notification_type: 'exploration_update' },
      '/vault/vault-1/exploration',
    ],
    [
      'the vault for a room unlock rather than a source dweller',
      { notification_type: 'room_unlocked', from_dweller_id: 'dweller-1' },
      '/vault/vault-1',
    ],
    [
      'the source dweller for a level-up',
      { notification_type: 'level_up', from_dweller_id: 'dweller-1' },
      '/vault/vault-1/dwellers/dweller-1',
    ],
    [
      'the returned quest reward modal',
      {
        notification_type: 'quest_complete',
        meta_data: { quest_id: 'quest-1', ready_to_claim: true },
      },
      '/vault/vault-1/quests?claimQuest=quest-1',
    ],
    [
      'the quest list for a quest that is not claimable',
      {
        notification_type: 'quest_complete',
        meta_data: { quest_id: 'quest-1', ready_to_claim: false },
      },
      '/vault/vault-1/quests',
    ],
    [
      'a settled duel from its combat notification',
      { notification_type: 'combat_victory', meta_data: { duel_id: 'duel-1' } },
      '/vault/vault-1/pvp?duel=duel-1',
    ],
    [
      'a settled Combat Zone bout from its combat notification',
      { notification_type: 'combat_victory', meta_data: { combat_zone_match_id: 'cz-1' } },
      '/vault/vault-1/map?combatZoneMatch=cz-1',
    ],
    [
      'the map for a cleared location',
      { notification_type: 'location_cleared' },
      '/vault/vault-1/map',
    ],
    [
      'the map place deep link for a ready location',
      { notification_type: 'location_ready', meta_data: { location_id: 'loc-1' } },
      '/vault/vault-1/map?place=loc-1',
    ],
  ])('opens %s', (_name, payload, expected) => {
    expect(route(payload as Record<string, unknown>)).toBe(expected)
  })
})

describe('getNotificationSound', () => {
  it.each([
    ['crafting_complete', 'craftComplete'],
    ['baby_born', 'babyBorn'],
    ['power_outage', 'powerOutage'],
  ])('gives %s its own cue instead of the generic alert', (type, cue) => {
    expect(getNotificationSound(type)).toBe(cue)
  })

  it('leaves combat on the generic alert so the incident stream does not double-play', () => {
    expect(['combat_started', 'combat_victory', 'combat_defeat'].map(getNotificationSound)).toEqual(
      ['notification', 'notification', 'notification']
    )
  })

  it.each([
    ['level_up', 'levelUp'],
    ['training_complete', 'trainingComplete'],
    ['radio_new_dweller', 'radioRecruit'],
    ['objective_completed', 'objectiveReady'],
    ['something_new', 'notification'],
  ])('maps %s to %s', (type, cue) => {
    expect(getNotificationSound(type)).toBe(cue)
  })
})

it.each([
  ['storage_item_degraded', 'resourceLow'],
  ['storage_item_upgraded', 'craftComplete'],
])('routes %s to storage', (notification_type, sound) => {
  expect(route({ notification_type })).toBe('/vault/vault-1/storage')
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
      expect(route({ notification_type, meta_data: { room_id: 'room-1' } })).toBe(
        '/vault/vault-1?roomId=room-1'
      )
    }
  )

  it('falls back to the vault when the room id is missing', () => {
    expect(route({ notification_type: 'rush_succeeded' })).toBe('/vault/vault-1')
  })

  it('gives each outcome a dedicated cue', () => {
    expect([getNotificationSound('rush_succeeded'), getNotificationSound('rush_failed')]).toEqual([
      'rushSuccess',
      'rushFail',
    ])
  })
})
