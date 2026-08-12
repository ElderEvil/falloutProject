import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RevivalSection from '@/modules/dwellers/components/death/RevivalSection.vue'

describe('RevivalSection', () => {
  it('uses the terminal-black surface instead of the default grey card surface', () => {
    const wrapper = mount(RevivalSection, {
      props: {
        dwellerId: 'dweller-1',
        revivalCost: {
          revival_cost: 250,
          vault_caps: 500,
          can_afford: true,
          days_until_permanent: 5,
        },
      },
      global: {
        stubs: {
          UCard: {
            inheritAttrs: false,
            template: '<section v-bind="$attrs"><slot /></section>',
          },
          UButton: true,
          UBadge: true,
          Icon: true,
        },
      },
    })

    expect(wrapper.find('.revival-section').classes()).toContain('!bg-terminal-background')
    expect(wrapper.find('.revival-section').classes()).toContain('!border-theme-primary/40')
    expect(wrapper.find('.bg-gray-900').exists()).toBe(false)
  })
})
