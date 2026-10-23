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
  it('renders caps with their label and amount', () => {
    const reward: GrantedReward = { reward_type: 'caps', amount: 25 }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:coins',
      label: 'Bottle Caps',
      value: '25',
    })
  })

  it('renders resources with their type-specific icon and label', () => {
    const reward: GrantedReward = { reward_type: 'resource', resource_type: 'food', amount: 10 }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:silverware',
      label: 'Food',
      value: '10',
    })
  })

  it('renders experience with the granted name when present, else the amount', () => {
    const named: GrantedReward = {
      reward_type: 'experience',
      amount: 100,
      name: 'Quest experience',
    }
    expect(describeGrantedReward(named).value).toBe('Quest experience')

    const unnamed: GrantedReward = { reward_type: 'experience', amount: 100 }
    expect(describeGrantedReward(unnamed).value).toBe('100 XP')
  })

  it('renders a granted dweller by name', () => {
    const reward: GrantedReward = { reward_type: 'dweller', dweller_id: 'd-1', name: 'Jane Doe' }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:account-plus',
      label: 'New Dweller',
      value: 'Jane Doe',
    })
  })

  it('renders medication with the quantity and its label', () => {
    const stimpak: GrantedReward = { reward_type: 'stimpak', amount: 5 }
    expect(describeGrantedReward(stimpak)).toEqual({
      icon: 'mdi:medical-bag',
      label: 'Stimpak',
      value: '5',
    })
  })

  it('renders an item with quantity prefix and type-specific icon and label', () => {
    const reward: GrantedReward = {
      reward_type: 'item',
      item_type: 'weapon',
      name: 'Rifle',
      amount: 3,
    }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:pistol',
      label: 'Weapon',
      value: '3x Rifle',
    })
  })

  it('renders a dweller-granting item reward with the dweller label and icon', () => {
    const reward: GrantedReward = {
      reward_type: 'item',
      item_type: 'dweller',
      name: 'Legendary Dweller',
      amount: 1,
    }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:account-plus',
      label: 'Dweller',
      value: 'Legendary Dweller',
    })
  })

  it('falls back to the generic item icon and label for an unknown item type', () => {
    const reward: GrantedReward = {
      reward_type: 'item',
      item_type: 'unknown',
      name: 'Mystery Trinket',
      amount: 1,
    }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:package-variant',
      label: 'Item',
      value: 'Mystery Trinket',
    })
  })

  it('renders a zero-amount medication as its bare label, like the backend summary', () => {
    const radaway: GrantedReward = { reward_type: 'radaway', amount: 0 }
    expect(describeGrantedReward(radaway).value).toBe('RadAway')
  })
})

describe('formatGrantedReward', () => {
  it('matches the backend format_reward_summary strings', () => {
    const caps: GrantedReward = { reward_type: 'caps', amount: 25 }
    const food: GrantedReward = { reward_type: 'resource', resource_type: 'food', amount: 10 }
    const box: GrantedReward = {
      reward_type: 'item',
      item_type: 'lunchbox',
      name: 'Lunchbox',
      amount: 1,
    }

    expect(formatGrantedReward(caps)).toBe('25 caps')
    expect(formatGrantedReward(food)).toBe('10 food')
    expect(formatGrantedReward(box)).toBe('Lunchbox')
  })

  it('renders named experience by name and unnamed by amount', () => {
    expect(
      formatGrantedReward({ reward_type: 'experience', amount: 100, name: 'Quest experience' })
    ).toBe('Quest experience')
    expect(formatGrantedReward({ reward_type: 'experience', amount: 100 })).toBe('100 XP')
  })

  it('renders a dweller by name and items with a quantity prefix', () => {
    expect(
      formatGrantedReward({ reward_type: 'dweller', dweller_id: 'd-1', name: 'Jane Doe' })
    ).toBe('Jane Doe')
    expect(
      formatGrantedReward({ reward_type: 'item', item_type: 'weapon', name: 'Rifle', amount: 3 })
    ).toBe('3x Rifle')
  })

  it('renders a zero-amount medication as its bare label, like the backend summary', () => {
    expect(formatGrantedReward({ reward_type: 'radaway', amount: 0 })).toBe('RadAway')
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

  it('shares the common reward-type icons with the granted-reward mapping', () => {
    expect(questRewardIcon(questReward({ reward_type: 'caps' }))).toBe('mdi:coins')
    expect(questRewardIcon(questReward({ reward_type: 'radaway' }))).toBe('mdi:radiation')
    expect(questRewardIcon(questReward({ reward_type: 'stimpak' }))).toBe('mdi:medical-bag')
    expect(questRewardIcon(questReward({ reward_type: 'lunchbox' }))).toBe('mdi:gift')
  })

  it('resolves resource rewards by their resource type', () => {
    expect(
      questRewardIcon(
        questReward({ reward_type: 'resource', reward_data: { resource_type: 'food' } })
      )
    ).toBe('mdi:silverware')
    expect(
      questRewardIcon(
        questReward({ reward_type: 'resource', reward_data: { resource_type: 'mystery' } })
      )
    ).toBe('mdi:database')
  })

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

  it('uses the item-type icon for dweller-granting item rewards', () => {
    expect(
      questRewardIcon(
        questReward({
          reward_type: 'item',
          reward_data: { item_type: 'dweller', item_name: 'Legendary Dweller' },
        })
      )
    ).toBe('mdi:account-plus')
  })
})

describe('questSlotLimitForVault', () => {
  const office = (tier: number) => ({ category: 'quests', tier })
  const production = { category: 'production', tier: 3 }

  it('uses the office tier as the slot count', () => {
    expect(questSlotLimitForVault([production, office(1)], 'vault-1', 'vault-1')).toBe(1)
    expect(questSlotLimitForVault([production, office(2)], 'vault-1', 'vault-1')).toBe(2)
    expect(questSlotLimitForVault([production, office(3)], 'vault-1', 'vault-1')).toBe(3)
  })

  it('returns zero without an office', () => {
    expect(questSlotLimitForVault([production], 'vault-1', 'vault-1')).toBe(0)
  })

  it("ignores another vault's rooms while the switch is loading", () => {
    expect(questSlotLimitForVault([office(3)], 'vault-1', 'vault-2')).toBe(0)
  })
})
