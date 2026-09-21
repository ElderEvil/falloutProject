import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import USkeleton from '@/core/components/ui/USkeleton.vue'

describe('USkeleton', () => {
  it('renders a placeholder div with default dimensions', () => {
    const wrapper = mountWithSetup(USkeleton)

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.attributes('style')).toContain('width: 100%')
    expect(wrapper.attributes('style')).toContain('height: 1rem')
  })

  it('applies custom width and height', () => {
    const wrapper = mountWithSetup(USkeleton, { props: { width: '200px', height: '3rem' } })

    expect(wrapper.attributes('style')).toContain('width: 200px')
    expect(wrapper.attributes('style')).toContain('height: 3rem')
  })

  it('renders no text content', () => {
    const wrapper = mountWithSetup(USkeleton)

    expect(wrapper.text()).toBe('')
  })

  it.each(['none', 'sm', 'md', 'lg', 'full'] as const)(
    'renders for the %s rounded variant',
    (rounded) => {
      const wrapper = mountWithSetup(USkeleton, { props: { rounded } })

      expect(wrapper.element.tagName).toBe('DIV')
      expect(wrapper.attributes('style')).toContain('width: 100%')
    },
  )

  it('renders without animation when animate is false', () => {
    const wrapper = mountWithSetup(USkeleton, { props: { animate: false } })

    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.attributes('style')).toContain('height: 1rem')
  })
})