import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ResourceBar from '@/components/common/ResourceBar.vue'

// Mock @iconify/vue
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>'
  }
}))

describe('ResourceBar', () => {
  describe('Props', () => {
    it('should render with required props', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
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
          icon: 'mdi:water'
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
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 50%')
    })

    it('should handle 0% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 0%')
    })

    it('should handle 100% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 100,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should cap at 100% when current exceeds max', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 150,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should calculate fractional percentages correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 33,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 33%')
    })
  })

  describe('Icon Rendering', () => {
    it('should render the icon component', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      expect(wrapper.find('.mock-icon').exists()).toBe(true)
    })

    it('should pass icon prop to Icon component', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:water'
        }
      })

      const icon = wrapper.find('.mock-icon')
      expect(icon.attributes('data-icon')).toBe('mdi:water')
    })
  })

  describe('Styling', () => {
    it('should have correct container structure', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const container = wrapper.find('.relative.flex.items-center.space-x-2')
      expect(container.exists()).toBe(true)
    })

    it('should have progress bar with correct classes', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const barContainer = wrapper.find('.h-6.w-40.rounded-full.border-2.border-gray-600.bg-gray-800')
      expect(barContainer.exists()).toBe(true)
    })

    it('should display text overlay with values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const overlay = wrapper.find('.absolute.inset-0')
      expect(overlay.exists()).toBe(true)
      expect(overlay.text()).toBe('75/100')
    })
  })

  describe('Status Colors', () => {
    it('should show red color for critical status (<=5%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 5,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('background-color: rgb(220, 38, 38)')
    })

    it('should show orange color for low status (<=20%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 20,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('background-color: rgb(249, 115, 22)')
    })

    it('should show yellow color for medium status (<=50%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('background-color: rgb(234, 179, 8)')
    })

    it('should show green color for healthy status (>50%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('background-color: var(--color-theme-primary)')
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero max value', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 0,
          icon: 'mdi:lightning-bolt'
        }
      })

      expect(wrapper.text()).toContain('0/0')
      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 0%')
    })

    it('should handle large numbers', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 9999,
          max: 10000,
          icon: 'mdi:lightning-bolt'
        }
      })

      expect(wrapper.text()).toContain('9999/10000')
      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 99.99%')
    })

    it('should handle negative current value gracefully', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: -10,
          max: 100,
          icon: 'mdi:lightning-bolt'
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
          icon: 'mdi:lightning-bolt'
        }
      })

      expect(wrapper.text()).toContain('50/100')

      await wrapper.setProps({ current: 75 })

      expect(wrapper.text()).toContain('75/100')
      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 75%')
    })

    it('should update percentage when max changes', async () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      let progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 50%')

      await wrapper.setProps({ max: 200 })

      progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 25%')
    })
  })

  describe('Label', () => {
    it('should display label when provided', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt',
          label: 'Power'
        }
      })

      expect(wrapper.text()).toContain('Power')
    })

    it('should not display label when not provided', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt'
        }
      })

      const label = wrapper.find('.text-xs.text-gray-400')
      expect(label.exists()).toBe(false)
    })
  })
})
