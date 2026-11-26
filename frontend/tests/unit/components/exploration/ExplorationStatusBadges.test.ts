import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { createExploration } from '../../helpers/explorationFixtures'
import { mount } from '@vue/test-utils'
import ExplorationStatusBadges from '@/modules/exploration/components/ExplorationStatusBadges.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller } from '@/modules/dwellers/models/dweller'

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" />', props: [] })
)

const exploration = createExploration()

const dweller = {
  first_name: 'Lucy',
  last_name: 'MacLean',
  health: 100,
  max_health: 100,
  radiation: 0,
} as Dweller

const mountBadges = (patch: Partial<Exploration> = {}, props: Record<string, unknown> = {}) =>
  mount(ExplorationStatusBadges, {
    props: { exploration: { ...exploration, ...patch }, dweller, ...props },
  })

const atClock = (time: string) => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(time))
}

describe('ExplorationStatusBadges', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('names the status chip EXPLORING for an active run that is not ready yet', () => {
    atClock('2026-01-01T01:00:00Z')
    const wrapper = mountBadges()

    expect(wrapper.text()).toContain('EXPLORING')
    expect(wrapper.text()).not.toContain('RETURNING')
    expect(wrapper.text()).not.toContain('READY')
    expect(wrapper.text()).not.toContain('AT RISK')
    // The chip is an img with an accessible name, not decorative text.
    const chip = wrapper.find('span[role="img"]')
    expect(chip.exists()).toBe(true)
    expect(chip.attributes('aria-label')).toBe('EXPLORING')
  })

  it('names the icon-only compact chip too', () => {
    atClock('2026-01-01T01:00:00Z')
    const chip = mountBadges({}, { compact: true }).find('span[role="img"]')

    expect(chip.exists()).toBe(true)
    expect(chip.attributes('aria-label')).toBe('EXPLORING')
    expect(chip.text()).not.toContain('EXPLORING')
  })

  it.each([
    [
      'RETURNING',
      '2026-01-01T01:00:00Z',
      {
        status: 'returning',
        return_started_at: '2026-01-01T00:00:00Z',
        return_completes_at: '2026-01-01T02:00:00Z',
      },
      ['EXPLORING', 'READY'],
    ],
    ['READY', '2026-01-01T09:00:00Z', {}, ['EXPLORING', 'RETURNING']],
  ] as [string, string, Partial<Exploration>, string[]][])(
    'shows %s when the run reaches that state',
    (expected, clock, patch, absent) => {
      atClock(clock)
      const wrapper = mountBadges(patch)

      expect(wrapper.text()).toContain(expected)
      for (const label of absent) expect(wrapper.text()).not.toContain(label)
    }
  )

  it('shows AT RISK for a dweller with low health', () => {
    atClock('2026-01-01T01:00:00Z')
    const wrapper = mountBadges(
      {},
      {
        dweller: { ...dweller, health: 20, max_health: 100, radiation: 10 },
      }
    )

    expect(wrapper.text()).toContain('AT RISK')
    expect(wrapper.find('[aria-label="Dweller at risk"]').exists()).toBe(true)
  })
})
