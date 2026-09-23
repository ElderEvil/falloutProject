import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import Progress from '@/core/components/ui/progress/Progress.vue'

function root(wrapper: ReturnType<typeof mountWithSetup>) {
  return wrapper.find('[data-slot="progress"]')
}

describe('Progress', () => {
  it('exposes progressbar semantics with the model value', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 42 } })

    expect(root(wrapper).attributes('role')).toBe('progressbar')
    expect(root(wrapper).attributes('aria-valuenow')).toBe('42')
    expect(root(wrapper).attributes('aria-valuemin')).toBe('0')
    expect(root(wrapper).attributes('aria-valuemax')).toBe('100')
  })

  it('names the meter from the label prop', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 10, label: 'Quest progress' } })

    expect(root(wrapper).attributes('aria-label')).toBe('Quest progress')
  })

  it('still accepts a caller-supplied aria-label when no label prop is given', () => {
    const wrapper = mountWithSetup(Progress, {
      props: { modelValue: 10, 'aria-label': 'Fallback name' },
    })

    expect(root(wrapper).attributes('aria-label')).toBe('Fallback name')
  })

  it('announces valueText as the accessible value', () => {
    const wrapper = mountWithSetup(Progress, {
      props: { modelValue: 45, label: 'Health', valueText: '45%' },
    })

    expect(root(wrapper).attributes('aria-valuetext')).toBe('45%')
  })

  it('defaults the fill to the theme primary token', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 50 } })

    expect(root(wrapper).attributes('style')).toContain('--progress-fill: var(--primary)')
  })

  it('maps a semantic tone to its token', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 50, tone: 'info' } })

    expect(root(wrapper).attributes('style')).toContain('--progress-fill: var(--color-info)')
  })

  it('lets an explicit fill override the tone', () => {
    const wrapper = mountWithSetup(Progress, {
      props: { modelValue: 50, tone: 'danger', fill: '#facc15' },
    })

    expect(root(wrapper).attributes('style')).toContain('--progress-fill: #facc15')
  })

  it('renders decorative segments without changing the announced value', () => {
    const wrapper = mountWithSetup(Progress, {
      props: { modelValue: 60, label: 'Exploration', segmented: true },
    })
    const segments = wrapper.find('[data-slot="progress-segments"]')

    expect(segments.exists()).toBe(true)
    expect(segments.attributes('aria-hidden')).toBe('true')
    expect(root(wrapper).attributes('aria-valuenow')).toBe('60')
  })

  it('omits the segment overlay when not segmented', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 60 } })

    expect(wrapper.find('[data-slot="progress-segments"]').exists()).toBe(false)
  })

  it('positions the indicator from the model value', () => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 30 } })

    expect(wrapper.find('[data-slot="progress-indicator"]').attributes('style')).toContain(
      'translateX(-70%)',
    )
  })

  it.each(['xs', 'sm', 'md'] as const)('renders the %s size as a progressbar', (size) => {
    const wrapper = mountWithSetup(Progress, { props: { modelValue: 50, size } })

    expect(root(wrapper).attributes('role')).toBe('progressbar')
  })

  it.each(['default', 'info', 'warning', 'danger', 'success'] as const)(
    'renders the %s tone as a progressbar',
    (tone) => {
      const wrapper = mountWithSetup(Progress, { props: { modelValue: 50, tone } })

      expect(root(wrapper).attributes('role')).toBe('progressbar')
    },
  )
})
