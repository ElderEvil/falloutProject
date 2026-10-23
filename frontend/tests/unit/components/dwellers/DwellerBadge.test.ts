import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import DwellerBadge from '@/modules/dwellers/components/DwellerBadge.vue'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
  getIdentityOptions: vi.fn().mockResolvedValue({ races: [], factions_by_race: {}, states_by_race: {} }),
}))

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" :data-icon="icon" />' })
)

const visualAttributes = {
  race: 'super_mutant',
  faction: 'the_institute',
  state_of_being: 'behemoth',
} as never

beforeEach(() => {
  setActivePinia(createPinia())
  const flags = useFeatureFlagsStore()
  flags.raceMechanics = true
  flags.factionMechanics = true
})

describe('DwellerBadge', () => {
  it('renders the icon with a visible label by default', () => {
    const wrapper = mount(DwellerBadge, {
      props: { icon: 'mdi:account', color: 'var(--badge-gender-male)', label: 'Male' },
    })

    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Male')
    expect(wrapper.find('[data-icon="mdi:account"]').exists()).toBe(true)
    expect(wrapper.find('.badge-label').text()).toBe('Male')
  })

  it('collapses to an icon-only chip when the label is hidden', () => {
    const wrapper = mount(DwellerBadge, {
      props: { icon: 'mdi:account', color: 'var(--badge-gender-male)', label: 'Male', showLabel: false },
    })

    expect(wrapper.find('.icon-only').exists()).toBe(true)
    expect(wrapper.find('.badge-label').exists()).toBe(false)
  })

  it('renders a monogram when no glyph exists for the fact', () => {
    const wrapper = mount(DwellerBadge, {
      props: { monogram: 'III', color: 'var(--badge-age-adult)', label: 'Behemoth', showLabel: false },
    })

    expect(wrapper.find('.badge-monogram').text()).toBe('III')
    expect(wrapper.find('.badge-icon').exists()).toBe(false)
  })

  it('adds a state marker and includes its description in the accessible name', () => {
    const wrapper = mount(DwellerBadge, {
      props: {
        icon: 'mdi:robot-outline',
        color: 'var(--badge-race-synth)',
        label: 'Synth',
        marker: { monogram: 'III', label: 'Gen III' },
      },
    })

    expect(wrapper.find('.badge-state-marker').text()).toBe('III')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toBe('Synth · Gen III')
  })

  it('describes the fact on hover without a native title', () => {
    const wrapper = mount(DwellerBadge, {
      props: { icon: 'mdi:account', color: 'var(--badge-age-adult)', label: 'Adult' },
    })

    expect(wrapper.html()).not.toContain('title=')
    expect(wrapper.find('[data-slot="tooltip-trigger"]').exists()).toBe(true)
  })
})

describe('DwellerIdentitySignal', () => {
  it('combines race and state, keeping faction as a separate badge', () => {
    const wrapper = mount(DwellerIdentitySignal, { props: { visualAttributes } })

    const badges = wrapper.findAll('.dweller-badge')
    expect(badges).toHaveLength(2)
    expect(badges[0].text()).toContain('Super Mutant')
    expect(badges[0].find('.badge-state-marker [data-icon="mdi:arm-flex"]').exists()).toBe(true)
    expect(badges[0].attributes('aria-label')).toBe('Super Mutant · Behemoth')
    expect(badges[1].text()).toContain('The Institute')
  })

  it('uses a state icon inside the race badge for ghouls', () => {
    const wrapper = mount(DwellerIdentitySignal, {
      props: { visualAttributes: { race: 'ghoul', state_of_being: 'feral' } as never },
    })

    const raceBadge = wrapper.find('.dweller-badge')
    expect(raceBadge.find('[data-icon="mdi:skull-outline"]').exists()).toBe(true)
    expect(raceBadge.attributes('aria-label')).toBe('Ghoul · Feral')
    expect(wrapper.findAll('.dweller-badge')).toHaveLength(1)
  })

  it('uses a Roman numeral marker for synth generation', () => {
    const wrapper = mount(DwellerIdentitySignal, {
      props: {
        visualAttributes: { race: 'synth', state_of_being: 'gen_2' } as never,
        compact: true,
      },
    })

    const badge = wrapper.find('.dweller-badge')
    expect(wrapper.findAll('.dweller-badge')).toHaveLength(1)
    expect(badge.find('[data-icon="mdi:robot-outline"]').exists()).toBe(true)
    expect(badge.find('.badge-state-marker').text()).toBe('II')
  })

  it('marks identity glyphs semantic-light: no hover vocabulary, theme-primary colour', () => {
    const wrapper = mount(DwellerIdentitySignal, { props: { visualAttributes, compact: true } })

    expect(wrapper.find('.transition-colors').exists()).toBe(false)
    expect(wrapper.find('.icon-only.size-sm').exists()).toBe(true)
  })

  it('falls back to a word-cased label for unknown values', () => {
    const wrapper = mount(DwellerIdentitySignal, {
      props: { visualAttributes: { race: 'unknown_race_origin' } as never },
    })

    expect(wrapper.find('.badge-label').text()).toBe('Unknown Race Origin')
  })
})
