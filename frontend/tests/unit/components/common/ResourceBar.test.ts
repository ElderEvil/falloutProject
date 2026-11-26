import { describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount, type MountingOptions, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ResourceBar from '@/modules/vault/components/shell/ResourceBar.vue'

// Mock @iconify/vue
vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

type ResourceBarProps = InstanceType<typeof ResourceBar>['$props']
type MountOptions = Omit<MountingOptions<typeof ResourceBar>, 'props'>

/** Mounts the bar with every required prop filled; callers override what the case needs. */
function render(props: Partial<ResourceBarProps> = {}, options: MountOptions = {}): VueWrapper {
  return mount(ResourceBar, {
    ...options,
    props: { current: 50, max: 100, icon: 'mdi:lightning-bolt', ...props } as ResourceBarProps,
  })
}

const progressBar = (wrapper: VueWrapper) => wrapper.get('.transition-all')

describe('ResourceBar', () => {
  describe('Props', () => {
    it.each([
      [50, 100, '50/100'],
      [75, 150, '75/150'],
    ])('renders %s/%s from the required props', (current, max, text) => {
      const wrapper = render({ current, max })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.text()).toContain(text)
    })
  })

  describe('Percentage Calculation', () => {
    it.each([
      ['normal values', 50, 100, 'width: 50%'],
      ['0%', 0, 100, 'width: 0%'],
      ['100%', 100, 100, 'width: 100%'],
      ['an over-max value, capped at 100%', 150, 100, 'width: 100%'],
      ['a fractional value', 33, 100, 'width: 33%'],
    ])('computes the width for %s', (_label, current, max, width) => {
      expect(progressBar(render({ current, max })).attributes('style')).toContain(width)
    })
  })

  describe('Icon Rendering', () => {
    it('renders the icon component with the icon prop', () => {
      const icon = render({ icon: 'mdi:water' }).find('.mock-icon')

      expect(icon.exists()).toBe(true)
      expect(icon.attributes('data-icon')).toBe('mdi:water')
    })
  })

  describe('Styling', () => {
    it('has the container and progress track structure', () => {
      const wrapper = render()

      expect(wrapper.find('.relative.flex.items-center.space-x-2').exists()).toBe(true)
      expect(
        wrapper.find('.h-6.w-40.rounded-full.border-2.border-border.bg-surface-raised').exists()
      ).toBe(true)
    })

    it('displays text overlay with values', () => {
      const overlay = render({ current: 75, max: 100 }).find('.absolute.inset-0')

      expect(overlay.exists()).toBe(true)
      expect(overlay.text()).toBe('75/100')
    })
  })

  describe('Status Colors', () => {
    it.each([
      ['red for critical status (<=5%)', 5, 'bg-danger'],
      ['orange for low status (<=20%)', 20, 'bg-warning'],
      ['yellow for medium status (<=50%)', 50, 'bg-caps'],
      ['green for healthy status (>50%)', 75, 'bg-theme-primary'],
    ])('shows %s', (_label, current, colorClass) => {
      expect(progressBar(render({ current })).classes()).toContain(colorClass)
    })
  })

  describe('Edge Cases', () => {
    it('should handle zero max value', () => {
      const wrapper = render({ current: 0, max: 0 })

      expect(wrapper.text()).toContain('0/0')
      expect(progressBar(wrapper).attributes('style')).toContain('width: 0%')
    })

    it('should handle large numbers', () => {
      const wrapper = render({ current: 9999, max: 10000 })

      expect(wrapper.text()).toContain('9999/10000')
      expect(progressBar(wrapper).attributes('style')).toContain('width: 99.99%')
    })

    it('should handle negative current value gracefully', () => {
      expect(render({ current: -10 }).text()).toContain('-10/100')
    })
  })

  describe('Reactivity', () => {
    it('should update when props change', async () => {
      const wrapper = render()

      expect(wrapper.text()).toContain('50/100')

      await wrapper.setProps({ current: 75 })

      expect(wrapper.text()).toContain('75/100')
      expect(progressBar(wrapper).attributes('style')).toContain('width: 75%')
    })

    it('should update percentage when max changes', async () => {
      const wrapper = render()

      expect(progressBar(wrapper).attributes('style')).toContain('width: 50%')

      await wrapper.setProps({ max: 200 })

      expect(progressBar(wrapper).attributes('style')).toContain('width: 25%')
    })
  })

  describe('Label', () => {
    it('should display label when provided', () => {
      expect(render({ label: 'Power' }).text()).toContain('Power')
    })

    it('should not display label when not provided', () => {
      expect(render().find('.text-xs.text-muted-foreground').exists()).toBe(false)
    })
  })

  describe('Resource forecast', () => {
    // Reka renders TooltipContent only when open and teleported; stub it inline so the
    // forecast text (the behavioral contract) is assertable without hover timers.
    const contentStub = { template: '<div><slot /></div>' }

    it('shows time to empty or full from the net rate', () => {
      const draining = render(
        { current: 30, icon: 'mdi:water', label: 'Water', productionRate: -5 },
        { global: { stubs: { TooltipContent: contentStub } } }
      )
      const filling = render(
        { current: 70, icon: 'mdi:food-apple', label: 'Food', productionRate: 5 },
        { global: { stubs: { TooltipContent: contentStub } } }
      )

      expect(draining.text()).toContain('Estimated empty: 6 min')
      expect(filling.text()).toContain('Estimated full: 6 min')
    })
  })

  describe('Critical drain warning', () => {
    const drainingProps = {
      current: 15,
      icon: 'mdi:food-apple',
      label: 'Food',
      productionRate: -5,
    }

    it('renders a persistent inline warning with the forecast while draining and low', () => {
      const wrapper = render(drainingProps)

      expect(wrapper.find('.critical-warning').exists()).toBe(true)
      expect(wrapper.text()).toContain('Food empty in ~3 min')
    })

    it('keeps the same forecast available in the tooltip', () => {
      const wrapper = render(drainingProps, {
        global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } },
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

      const wrapper = render(
        { ...drainingProps, criticalTo: '/vault/vault-1?roomId=room-9' },
        { global: { plugins: [router] } }
      )

      const link = wrapper.find('a.critical-warning')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toBe('/vault/vault-1?roomId=room-9')
      expect(link.attributes('aria-label')).toContain('Food empty in ~3 min')
    })

    it('stays silent unless the resource is both draining and low', () => {
      expect(
        render({ ...drainingProps, current: 50 })
          .find('.critical-warning')
          .exists()
      ).toBe(false)
      expect(
        render({ ...drainingProps, productionRate: 5 })
          .find('.critical-warning')
          .exists()
      ).toBe(false)
    })
  })
})
