import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerBadge from '@/modules/dwellers/components/DwellerBadge.vue'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span class="icon-mock" :data-icon="icon" />',
  },
}))

const visualAttributes = {
  race: 'super_mutant',
  faction: 'the_institute',
  state_of_being: 'behemoth',
} as never

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

  it('describes the fact on hover without a native title', () => {
    const wrapper = mount(DwellerBadge, {
      props: { icon: 'mdi:account', color: 'var(--badge-age-adult)', label: 'Adult' },
    })

    expect(wrapper.html()).not.toContain('title=')
    expect(wrapper.findComponent({ name: 'UTooltip' }).exists()).toBe(true)
  })
})

describe('DwellerIdentitySignal', () => {
  it('renders race, faction and state through the shared badge primitive', () => {
    const wrapper = mount(DwellerIdentitySignal, { props: { visualAttributes } })

    const badges = wrapper.findAll('.dweller-badge')
    expect(badges).toHaveLength(3)
    expect(badges[0].text()).toContain('Super Mutant')
    expect(badges[2].find('.badge-monogram').text()).toBe('III')
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
