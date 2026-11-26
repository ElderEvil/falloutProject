import { describe, expect, it } from 'vite-plus/test'
import {
  describeGrantedReward,
  formatGrantedReward,
  questRewardIcon,
  questSlotLimitForVault,
  type GrantedReward,
  type QuestReward,
} from '@/modules/progression/models/quest'

/**
 * Frontend display contract for settled rewards.
 *
 * The backend owns the wire shape (`GrantedReward` discriminated union, validated
 * by `granted_reward_adapter`) and a single summary renderer (`format_reward_summary`
 * in `app/schemas/rewards.py`). These tests lock the frontend presentation
 * (`describeGrantedReward` / `formatGrantedReward`) to that same contract so every
 * surface — toast, completion modal, reward cards — renders exactly what settlement
 * delivered. The `formatGrantedReward` strings deliberately mirror
 * `test_format_reward_summary_covers_variants` on the backend.
 */

describe('describeGrantedReward', () => {
  it.each<[string, GrantedReward, object]>([
    [
      'caps',
      { reward_type: 'caps', amount: 25 },
      { icon: 'mdi:coins', label: 'Bottle Caps', value: '25' },
    ],
    [
      'a resource',
      { reward_type: 'resource', resource_type: 'food', amount: 10 },
      { icon: 'mdi:silverware', label: 'Food', value: '10' },
    ],
    [
      'a granted dweller',
      { reward_type: 'dweller', dweller_id: 'd-1', name: 'Jane Doe' },
      { icon: 'mdi:account-plus', label: 'New Dweller', value: 'Jane Doe' },
    ],
    [
      'medication',
      { reward_type: 'stimpak', amount: 5 },
      { icon: 'mdi:medical-bag', label: 'Stimpak', value: '5' },
    ],
    [
      'a typed item',
      { reward_type: 'item', item_type: 'weapon', name: 'Rifle', amount: 3 },
      { icon: 'mdi:pistol', label: 'Weapon', value: '3x Rifle' },
    ],
    [
      'an item that grants a dweller',
      { reward_type: 'item', item_type: 'dweller', name: 'Legendary Dweller', amount: 1 },
      { icon: 'mdi:account-plus', label: 'Dweller', value: 'Legendary Dweller' },
    ],
    [
      'an unknown item type',
      { reward_type: 'item', item_type: 'unknown', name: 'Mystery Trinket', amount: 1 },
      { icon: 'mdi:package-variant', label: 'Item', value: 'Mystery Trinket' },
    ],
  ])('renders %s with their icon, label and value', (_, reward, expected) => {
    expect(describeGrantedReward(reward)).toEqual(expected)
  })

  it('renders experience with the granted name when present, else the amount', () => {
    expect(
      describeGrantedReward({ reward_type: 'experience', amount: 100, name: 'Quest experience' })
        .value
    ).toBe('Quest experience')
    expect(describeGrantedReward({ reward_type: 'experience', amount: 100 }).value).toBe('100 XP')
  })

  it('renders a zero-amount medication as its bare label, like the backend summary', () => {
    expect(describeGrantedReward({ reward_type: 'radaway', amount: 0 }).value).toBe('RadAway')
  })
})

describe('formatGrantedReward', () => {
  it.each<[string, GrantedReward, string]>([
    ['caps', { reward_type: 'caps', amount: 25 }, '25 caps'],
    ['food', { reward_type: 'resource', resource_type: 'food', amount: 10 }, '10 food'],
    [
      'a lunchbox',
      { reward_type: 'item', item_type: 'lunchbox', name: 'Lunchbox', amount: 1 },
      'Lunchbox',
    ],
    [
      'named experience',
      { reward_type: 'experience', amount: 100, name: 'Quest experience' },
      'Quest experience',
    ],
    ['unnamed experience', { reward_type: 'experience', amount: 100 }, '100 XP'],
    ['a dweller', { reward_type: 'dweller', dweller_id: 'd-1', name: 'Jane Doe' }, 'Jane Doe'],
    [
      'a stack of items',
      { reward_type: 'item', item_type: 'weapon', name: 'Rifle', amount: 3 },
      '3x Rifle',
    ],
    ['a zero-amount medication', { reward_type: 'radaway', amount: 0 }, 'RadAway'],
  ])('matches the backend format_reward_summary string for %s', (_, reward, expected) => {
    expect(formatGrantedReward(reward)).toBe(expected)
  })
})

describe('questRewardIcon', () => {
  const questReward = (overrides: Partial<QuestReward> = {}): QuestReward => ({
    id: 'reward-1',
    quest_id: 'quest-1',
    reward_type: 'caps',
    reward_data: {},
    reward_chance: 1,
    ...overrides,
  })

  it.each([
    ['caps', {}, 'mdi:coins'],
    ['radaway', {}, 'mdi:radiation'],
    ['stimpak', {}, 'mdi:medical-bag'],
    ['lunchbox', {}, 'mdi:gift'],
    ['resource', { resource_type: 'food' }, 'mdi:silverware'],
    ['resource', { resource_type: 'mystery' }, 'mdi:database'],
    ['item', { item_type: 'dweller', item_name: 'Legendary Dweller' }, 'mdi:account-plus'],
  ])(
    'shares the common %s icon mapping (with the granted-reward vocabulary)',
    (reward_type, reward_data, icon) => {
      expect(questRewardIcon(questReward({ reward_type, reward_data }))).toBe(icon)
    }
  )

  it('keeps item rewards on category, then name, then the generic fallback', () => {
    expect(
      questRewardIcon(
        questReward({
          reward_type: 'item',
          reward_data: { item_type: 'weapon', item_name: 'Rifle' },
        })
      )
    ).toBe('mdi:pistol')
    expect(
      questRewardIcon(questReward({ reward_type: 'item', reward_data: { item_name: 'RadAway' } }))
    ).toBe('mdi:radiation')
    expect(
      questRewardIcon(
        questReward({ reward_type: 'item', reward_data: { item_name: 'Mystery Trinket' } })
      )
    ).toBe('mdi:package-variant')
  })
})

describe('questSlotLimitForVault', () => {
  const office = (tier: number) => ({ category: 'quests', tier })
  const production = { category: 'production', tier: 3 }

  it.each([
    [1, 1],
    [2, 2],
    [3, 3],
  ])('uses office tier %i as the slot count', (tier, slots) => {
    expect(questSlotLimitForVault([production, office(tier)], 'vault-1', 'vault-1')).toBe(slots)
  })

  it('returns zero without an office', () => {
    expect(questSlotLimitForVault([production], 'vault-1', 'vault-1')).toBe(0)
  })

  it("ignores another vault's rooms while the switch is loading", () => {
    expect(questSlotLimitForVault([office(3)], 'vault-1', 'vault-2')).toBe(0)
  })
})
