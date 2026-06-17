import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UCard from '@/core/components/ui/UCard.vue'

describe('UCard (CRT Consistency)', () => {
  it('should not have inline style on title element', () => {
    const wrapper = mount(UCard, {
      props: { title: 'Test Card' },
      slots: { default: '<p>Content</p>' },
    })
    const title = wrapper.find('h3')
    // Should use Tailwind class not inline style
    expect(title.attributes('style')).toBeUndefined()
  })

  it('should use text-theme-primary class instead of inline color', () => {
    const wrapper = mount(UCard, {
      props: { title: 'Test Card' },
      slots: { default: '<p>Content</p>' },
    })
    const title = wrapper.find('h3')
    expect(title.classes()).toContain('text-theme-primary')
  })
})
