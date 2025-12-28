import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ResourceBar from '@/components/common/ResourceBar.vue'

const TEST_ICON = 'i-lucide-zap'

describe('ResourceBar', () => {
  describe('Props', () => {
    it('should render with required props', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.text()).toContain('50/100')
    })

    it('should display correct current and max values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 150,
          icon: TEST_ICON
        }
      })

      expect(wrapper.text()).toContain('75/150')
    })
  })

  describe('Percentage Calculation', () => {
    it('should calculate correct percentage for normal values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 50%')
    })

    it('should handle 0% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 100,
          icon: TEST_ICON
        }
      })

      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 0%')
    })

    it('should handle 100% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 100,
          max: 100,
          icon: TEST_ICON
        }
      })

      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should cap at 100% when current exceeds max', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 150,
          max: 100,
          icon: TEST_ICON
        }
      })

      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should calculate fractional percentages correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 33,
          max: 100,
          icon: TEST_ICON
        }
      })

      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 33%')
    })
  })

  describe('Icon Rendering', () => {
    it('should render the provided icon', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      // Icon should be rendered as SVG
      const svg = wrapper.find('svg')
      expect(svg.exists()).toBe(true)
    })
  })

  describe('Styling', () => {
    it('should have correct container structure', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      const container = wrapper.find('.flex.items-center')
      expect(container.exists()).toBe(true)
    })

    it('should display text overlay with values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 100,
          icon: TEST_ICON
        }
      })

      const overlay = wrapper.find('.absolute.inset-0')
      expect(overlay.exists()).toBe(true)
      expect(overlay.text()).toBe('75/100')
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero max value', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 0,
          icon: TEST_ICON
        }
      })

      expect(wrapper.text()).toContain('0/0')
      // When max is 0, percentage should be 100% to avoid division by zero issues
      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toBeDefined()
    })

    it('should handle large numbers', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 9999,
          max: 10000,
          icon: TEST_ICON
        }
      })

      expect(wrapper.text()).toContain('9999/10000')
      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 99.99%')
    })

    it('should handle negative current value gracefully', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: -10,
          max: 100,
          icon: TEST_ICON
        }
      })

      expect(wrapper.text()).toContain('-10/100')
    })
  })

  describe('Reactivity', () => {
    it('should update when props change', async () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      expect(wrapper.text()).toContain('50/100')

      await wrapper.setProps({ current: 75 })

      expect(wrapper.text()).toContain('75/100')
      const progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 75%')
    })

    it('should update percentage when max changes', async () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: TEST_ICON
        }
      })

      let progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 50%')

      await wrapper.setProps({ max: 200 })

      progressBar = wrapper.find('.bg-primary-500')
      expect(progressBar.attributes('style')).toContain('width: 25%')
    })
  })
})
