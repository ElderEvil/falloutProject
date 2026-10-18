import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Progress } from '@/core/components/ui/progress'
import ObjectiveCard from '@/modules/progression/components/ObjectiveCard.vue'
import type { Objective } from '@/modules/progression/models/objective'

const objective = (overrides: Partial<Objective> = {}): Objective => ({
  id: '4',
  vault_id: 'v1',
  challenge: 'Collect caps',
  progress: 100,
  total: 100,
  reward: '50 Caps',
  is_completed: false,
  category: 'daily',
  created_at: '',
  ...overrides,
})

// The claim action is a shadcn Button, so target it by its visible label rather
// than by an internal class name that the shared shell may rename.
const findButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))

describe('ObjectiveCard', () => {
  it.each([
    ['weapon:rare:Hardened shotgun', 'Rare Hardened shotgun'],
    ['outfit:Wasteland gear', 'Common Wasteland gear'],
    ['DWELLER:Wanderer', 'Wanderer'],
    ['50 Caps', '50 Caps'],
  ])('previews %s with rarity only for equipment', (reward, expected) => {
    const card = mount(ObjectiveCard, { props: { objective: objective({ reward }) } })
    expect(card.get('.reward-value').text()).toBe(expected)
    card.unmount()
  })

  it('uses the shared progress bar with the objective percentage', () => {
    const progressBar = mount(ObjectiveCard, {
      props: { objective: objective({ id: '1', progress: 40 }) },
    }).findComponent(Progress)
    expect(progressBar.exists()).toBe(true)
    expect(progressBar.props()).toMatchObject({ modelValue: 40 })
    expect(progressBar.find('[aria-label="Objective progress"]').exists()).toBe(true)
  })

  it('marks a completed objective with visible Completed text and drops the claim action', () => {
    const card = mount(ObjectiveCard, {
      props: { objective: objective({ id: '2', is_completed: true }) },
    })
    expect(card.text()).toContain('Completed')
    expect(findButton(card, 'Claim Reward')).toBeUndefined()
  })

  it('offers an enabled Claim Reward action for a finished objective awaiting its claim', () => {
    const card = mount(ObjectiveCard, {
      props: { objective: objective({ id: '4' }) },
    })
    expect(card.text()).not.toContain('Completed')
    expect(findButton(card, 'Claim Reward')?.attributes('disabled')).toBeUndefined()
  })

  it('disables the Claim Reward action while the claim is in flight', () => {
    const card = mount(ObjectiveCard, {
      props: { objective: objective({ id: '4' }), claiming: true },
    })
    expect(findButton(card, 'Claim Reward')?.attributes('disabled')).toBeDefined()
  })

  it('emits the claim event with the objective id when Claim Reward is pressed', async () => {
    const card = mount(ObjectiveCard, {
      props: { objective: objective({ id: '4' }) },
    })
    await findButton(card, 'Claim Reward')?.trigger('click')
    expect(card.emitted('claim')).toEqual([['4']])
  })

  it('separates the counting-rule note from the progress block with the divider', () => {
    const card = mount(ObjectiveCard, {
      props: {
        objective: objective({
          id: '5',
          target_entity: { production_only: true },
        }),
      },
    })
    const order = (selector: string) => {
      const nodes = [...card.element.querySelectorAll('*')]
      return nodes.findIndex((node) => node.matches(selector))
    }
    const note = order('.objective-note')
    const divider = order('.progression-divider')
    const progress = order('[aria-label="Objective progress"]')
    const claim = order('button')
    expect(note).toBeGreaterThanOrEqual(0)
    expect(divider).toBeGreaterThan(note)
    expect(progress).toBeGreaterThan(divider)
    expect(claim).toBeGreaterThan(divider)
  })

  it.each([
    ['production_only', 'Production counts even when storage is full.'],
    ['distinct_dwellers', 'Each dweller counts once for this objective.'],
  ])('explains the %s counting rule', (rule, message) => {
    const withRule = objective({
      id: '3',
      challenge: 'Collect power',
      progress: 10,
      total: 150,
      reward: '15 caps',
      target_entity: { [rule]: true },
    })
    const card = mount(ObjectiveCard, { props: { objective: withRule } })
    expect(card.text()).toContain(message)
    const ordinary = mount(ObjectiveCard, {
      props: { objective: { ...withRule, target_entity: {} } },
    })
    expect(ordinary.text()).not.toContain(message)
  })
  it('explains fresh achievement stages and previews the next target', () => {
    const card = mount(ObjectiveCard, {
      props: {
        objective: objective({
          id: 'water-track',
          category: 'achievement',
          track_key: 'collect:water',
          sequence: 1,
          next_stage_challenge: 'Collect 500 Water',
        }),
      },
    })
    expect(card.text()).toContain('Stage 1')
    expect(card.text()).toContain('Each stage starts at zero')
    expect(card.text()).toContain('Next stage: Collect 500 Water')
  })

  it('shows the reset time and protects earned rewards in the explanation', () => {
    const card = mount(ObjectiveCard, {
      props: {
        objective: objective({
          id: 'daily-water',
          category: 'daily',
          resets_at: '2026-10-20T00:00:00Z',
        }),
      },
    })
    expect(card.text()).toContain('Next reset:')
    expect(card.text()).toContain('Earned rewards stay claimable')
  })
})
