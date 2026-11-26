import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vite-plus/test'
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

const mountCard = (overrides: Partial<Objective> = {}, props: Record<string, unknown> = {}) =>
  mount(ObjectiveCard, { props: { objective: objective(overrides), ...props } })

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
    expect(mountCard({ reward }).get('.reward-value').text()).toBe(expected)
  })

  it('uses the shared progress bar with the objective percentage', () => {
    const progressBar = mountCard({ id: '1', progress: 40 }).findComponent(Progress)

    expect(progressBar.exists()).toBe(true)
    expect(progressBar.props()).toMatchObject({ modelValue: 40 })
    expect(progressBar.find('[aria-label="Objective progress"]').exists()).toBe(true)
  })

  it('marks a completed objective with visible Completed text and drops the claim action', () => {
    const card = mountCard({ id: '2', is_completed: true })

    expect(card.text()).toContain('Completed')
    expect(findButton(card, 'Claim Reward')).toBeUndefined()
  })

  it('offers an enabled Claim Reward action for a finished objective awaiting its claim', () => {
    const card = mountCard()

    expect(card.text()).not.toContain('Completed')
    expect(findButton(card, 'Claim Reward')?.attributes('disabled')).toBeUndefined()
  })

  it('disables the Claim Reward action while the claim is in flight', () => {
    expect(
      findButton(mountCard({}, { claiming: true }), 'Claim Reward')?.attributes('disabled')
    ).toBeDefined()
  })

  it('emits the claim event with the objective id when Claim Reward is pressed', async () => {
    const card = mountCard()

    await findButton(card, 'Claim Reward')?.trigger('click')

    expect(card.emitted('claim')).toEqual([['4']])
  })

  it.each([
    ['production_only', 'Production counts even when storage is full.'],
    ['distinct_dwellers', 'Each dweller counts once for this objective.'],
  ])('keeps the %s counting rule out of the card', (rule, message) => {
    const withRule = {
      id: '3',
      challenge: 'Collect power',
      progress: 10,
      total: 150,
      reward: '15 caps',
      target_entity: { [rule]: true },
    }

    expect(mountCard(withRule).text()).not.toContain(message)
    expect(mountCard({ ...withRule, target_entity: {} }).text()).not.toContain(message)
  })

  it('shows the current goal without stage mechanics or next-stage previews', () => {
    const card = mountCard({
      id: 'water-track',
      category: 'achievement',
      track_key: 'collect:water',
      sequence: 1,
      next_stage_challenge: 'Collect 500 Water',
    })

    expect(card.text()).not.toContain('Stage 1')
    expect(card.text()).toContain('Collect caps')
    expect(card.text()).toContain('50 Caps')
    expect(card.text()).not.toContain('Each stage starts at zero')
    expect(card.text()).not.toContain('Collect 500 Water')
  })

  it('keeps reset schedules and reward-retention rules out of the card', () => {
    const card = mountCard({ id: 'daily-water', resets_at: '2026-10-20T00:00:00Z' })

    expect(card.text()).not.toContain('Next reset:')
    expect(card.text()).not.toContain('Earned rewards stay claimable')
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
    expect(mountCard(details).get('.progression-description').text()).toBe(description)
  })

  it('keeps an authored mission description', () => {
    const card = mountCard({
      objective_type: 'collect',
      target_entity: { resource_type: 'water' },
      description: 'Fresh water is the first step toward a thriving vault.',
    })

    expect(card.get('.progression-description').text()).toBe(
      'Fresh water is the first step toward a thriving vault.'
    )
  })
})
