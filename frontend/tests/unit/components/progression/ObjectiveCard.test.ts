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

  it('separates the goal from progress and the claim action with the divider', () => {
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
    const title = order('.progression-title')
    const divider = order('.progression-divider')
    const progress = order('[aria-label="Objective progress"]')
    const claim = order('button')
    expect(title).toBeGreaterThanOrEqual(0)
    expect(divider).toBeGreaterThan(title)
    expect(progress).toBeGreaterThan(divider)
    expect(claim).toBeGreaterThan(divider)
  })

  it.each([
    ['production_only', 'Production counts even when storage is full.'],
    ['distinct_dwellers', 'Each dweller counts once for this objective.'],
  ])('keeps the %s counting rule out of the card', (rule, message) => {
    const withRule = objective({
      id: '3',
      challenge: 'Collect power',
      progress: 10,
      total: 150,
      reward: '15 caps',
      target_entity: { [rule]: true },
    })
    const card = mount(ObjectiveCard, { props: { objective: withRule } })
    expect(card.text()).not.toContain(message)
    const ordinary = mount(ObjectiveCard, {
      props: { objective: { ...withRule, target_entity: {} } },
    })
    expect(ordinary.text()).not.toContain(message)
  })
  it('shows the current goal without stage mechanics or next-stage previews', () => {
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
    expect(card.text()).not.toContain('Stage 1')
    expect(card.text()).toContain('Collect caps')
    expect(card.text()).toContain('50 Caps')
    expect(card.text()).not.toContain('Each stage starts at zero')
    expect(card.text()).not.toContain('Collect 500 Water')
  })

  it('keeps reset schedules and reward-retention rules out of the card', () => {
    const card = mount(ObjectiveCard, {
      props: {
        objective: objective({
          id: 'daily-water',
          category: 'daily',
          resets_at: '2026-10-20T00:00:00Z',
        }),
      },
    })
    expect(card.text()).not.toContain('Next reset:')
    expect(card.text()).not.toContain('Earned rewards stay claimable')
  })
})

it.each([
  [
    { objective_type: 'collect', target_entity: { resource_type: 'water' } },
    'Keep the taps running. Every drop helps the vault.',
  ],
  [
    { objective_type: 'assign_correct', target_entity: { distinct_dwellers: true } },
    'The right resident in the right room. Put different dwellers’ talents to work.',
  ],
] as const)('gives the goal a short vault-aware description', (details, description) => {
  const card = mount(ObjectiveCard, { props: { objective: objective(details) } })
  expect(card.get('.progression-description').text()).toBe(description)
})

it('keeps an authored mission description', () => {
  const card = mount(ObjectiveCard, {
    props: {
      objective: objective({
        objective_type: 'collect',
        target_entity: { resource_type: 'water' },
        description: 'Fresh water is the first step toward a thriving vault.',
      }),
    },
  })
  expect(card.get('.progression-description').text()).toBe(
    'Fresh water is the first step toward a thriving vault.'
  )
})
