import { describe, it, expect, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ResourceBar from '@/modules/vault/components/shell/ResourceBar.vue'

// Mock @iconify/vue
vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

describe('ResourceBar', () => {
  describe('Props', () => {
    it('should render with required props', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.text()).toContain('50/100')
    })

    it('should display correct current and max values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 150,
          icon: 'mdi:water',
        },
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
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 50%')
    })

    it('should handle 0% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 0%')
    })

    it('should handle 100% correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 100,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should cap at 100% when current exceeds max', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 150,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.attributes('style')).toContain('width: 100%')
    })

    it('should calculate fractional percentages correctly', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 33,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
      })

      expect(wrapper.find('.mock-icon').exists()).toBe(true)
    })

    it('should pass icon prop to Icon component', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:water',
        },
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
          icon: 'mdi:lightning-bolt',
        },
      })

      const container = wrapper.find('.relative.flex.items-center.space-x-2')
      expect(container.exists()).toBe(true)
    })

    it('should have progress bar with correct classes', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const barContainer = wrapper.find(
        '.h-6.w-40.rounded-full.border-2.border-stone-600.bg-stone-800'
      )
      expect(barContainer.exists()).toBe(true)
    })

    it('should display text overlay with values', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.classes()).toContain('bg-danger')
    })

    it('should show orange color for low status (<=20%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 20,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.classes()).toContain('bg-warning')
    })

    it('should show yellow color for medium status (<=50%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.classes()).toContain('bg-yellow-500')
    })

    it('should show green color for healthy status (>50%)', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 75,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const progressBar = wrapper.find('.transition-all')
      expect(progressBar.classes()).toContain('bg-theme-primary')
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero max value', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 0,
          max: 0,
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
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
          icon: 'mdi:lightning-bolt',
        },
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
          label: 'Power',
        },
      })

      expect(wrapper.text()).toContain('Power')
    })

    it('should not display label when not provided', () => {
      const wrapper = mount(ResourceBar, {
        props: {
          current: 50,
          max: 100,
          icon: 'mdi:lightning-bolt',
        },
      })

      const label = wrapper.find('.text-xs.text-gray-400')
      expect(label.exists()).toBe(false)
    })
  })

  describe('Resource forecast', () => {
    it('shows time to empty or full from the net rate', () => {
      // Reka renders TooltipContent only when open and teleported; stub it inline so the
      // forecast text (the behavioral contract) is assertable without hover timers.
      const contentStub = { template: '<div><slot /></div>' }
      const draining = mount(ResourceBar, {
        props: {
          current: 30,
          max: 100,
          icon: 'mdi:water',
          label: 'Water',
          productionRate: -5,
        },
        global: { stubs: { TooltipContent: contentStub } },
      })
      const filling = mount(ResourceBar, {
        props: {
          current: 70,
          max: 100,
          icon: 'mdi:food-apple',
          label: 'Food',
          productionRate: 5,
        },
        global: { stubs: { TooltipContent: contentStub } },
      })

      expect(draining.text()).toContain('Estimated empty: 6 min')
      expect(filling.text()).toContain('Estimated full: 6 min')
    })
  })

  describe('Critical drain warning', () => {
    const drainingProps = {
      current: 15,
      max: 100,
      icon: 'mdi:food-apple',
      label: 'Food',
      productionRate: -5,
    }

    it('renders a persistent inline warning with the forecast while draining and low', () => {
      const wrapper = mount(ResourceBar, { props: drainingProps })

      expect(wrapper.find('.critical-warning').exists()).toBe(true)
      expect(wrapper.text()).toContain('Food empty in ~3 min')
    })

    it('keeps the same forecast available in the tooltip', () => {
      const contentStub = { template: '<div><slot /></div>' }
      const wrapper = mount(ResourceBar, {
        props: drainingProps,
        global: { stubs: { TooltipContent: contentStub } },
      })

      expect(wrapper.text()).toContain('Estimated empty: 3 min')
    })

    it('links the warning to the production room route', async () => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
      })
      await router.push('/vault/vault-1')
      await router.isReady()

      const wrapper = mount(ResourceBar, {
        props: { ...drainingProps, criticalTo: '/vault/vault-1?roomId=room-9' },
        global: { plugins: [router] },
      })

      const link = wrapper.find('a.critical-warning')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toBe('/vault/vault-1?roomId=room-9')
      expect(link.attributes('aria-label')).toContain('Food empty in ~3 min')
    })

    it('stays silent unless the resource is both draining and low', () => {
      const medium = mount(ResourceBar, {
        props: { ...drainingProps, current: 50 },
      })
      const filling = mount(ResourceBar, {
        props: { ...drainingProps, productionRate: 5 },
      })

      expect(medium.find('.critical-warning').exists()).toBe(false)
      expect(filling.find('.critical-warning').exists()).toBe(false)
    })
  })
})
