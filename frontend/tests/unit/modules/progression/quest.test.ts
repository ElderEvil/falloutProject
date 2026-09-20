import { describe, expect, it } from 'vitest'
import { describeGrantedReward, formatGrantedReward, type GrantedReward } from '@/modules/progression/models/quest'

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
      icon: 'mdi:currency-usd',
      label: 'Bottle Caps',
      value: '25',
    })
  })

  it('renders resources with their type-specific icon and label', () => {
    const reward: GrantedReward = { reward_type: 'resource', resource_type: 'food', amount: 10 }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:food-apple',
      label: 'Food',
      value: '10',
    })
  })

  it('renders experience with the granted name when present, else the amount', () => {
    const named: GrantedReward = { reward_type: 'experience', amount: 100, name: 'Quest experience' }
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
    const reward: GrantedReward = { reward_type: 'item', item_type: 'weapon', name: 'Rifle', amount: 3 }
    expect(describeGrantedReward(reward)).toEqual({
      icon: 'mdi:sword-cross',
      label: 'Weapon',
      value: '3x Rifle',
    })
  })

  it('falls back to the generic item icon and label for an unknown item type', () => {
    const reward: GrantedReward = { reward_type: 'item', item_type: 'pet', name: 'Dogmeat', amount: 1 }
    expect(describeGrantedReward(reward).value).toBe('Dogmeat')
    expect(describeGrantedReward(reward).icon).toBe('mdi:paw')
    expect(describeGrantedReward(reward).label).toBe('Pet')
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
    const box: GrantedReward = { reward_type: 'item', item_type: 'lunchbox', name: 'Lunchbox', amount: 1 }

    expect(formatGrantedReward(caps)).toBe('25 caps')
    expect(formatGrantedReward(food)).toBe('10 food')
    expect(formatGrantedReward(box)).toBe('Lunchbox')
  })

  it('renders named experience by name and unnamed by amount', () => {
    expect(formatGrantedReward({ reward_type: 'experience', amount: 100, name: 'Quest experience' })).toBe(
      'Quest experience'
    )
    expect(formatGrantedReward({ reward_type: 'experience', amount: 100 })).toBe('100 XP')
  })

  it('renders a dweller by name and items with a quantity prefix', () => {
    expect(formatGrantedReward({ reward_type: 'dweller', dweller_id: 'd-1', name: 'Jane Doe' })).toBe('Jane Doe')
    expect(formatGrantedReward({ reward_type: 'item', item_type: 'weapon', name: 'Rifle', amount: 3 })).toBe('3x Rifle')
  })

  it('renders a zero-amount medication as its bare label, like the backend summary', () => {
    expect(formatGrantedReward({ reward_type: 'radaway', amount: 0 })).toBe('RadAway')
  })
})