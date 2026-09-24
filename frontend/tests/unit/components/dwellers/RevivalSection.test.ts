import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RevivalSection from '@/modules/dwellers/components/death/RevivalSection.vue'

const affordable = {
  revival_cost: 250,
  vault_caps: 500,
  can_afford: true,
  days_until_permanent: 5,
}

describe('RevivalSection', () => {
  it('renders the revival cost and current vault funds', () => {
    const wrapper = mount(RevivalSection, {
      props: { dwellerId: 'dweller-1', revivalCost: affordable },
    })

    expect(wrapper.text()).toContain('250')
    expect(wrapper.text()).toContain('500')
  })

  it('emits revive for an affordable dweller when the action is pressed', async () => {
    const wrapper = mount(RevivalSection, {
      props: { dwellerId: 'dweller-1', revivalCost: affordable },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('revive')).toEqual([['dweller-1']])
  })

  it('disables the action and warns when funds are insufficient', async () => {
    const wrapper = mount(RevivalSection, {
      props: {
        dwellerId: 'dweller-1',
        revivalCost: { ...affordable, can_afford: false, vault_caps: 10 },
      },
    })

    expect(wrapper.text()).toContain('INSUFFICIENT FUNDS FOR PROCEDURE')

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(wrapper.emitted('revive')).toBeUndefined()
  })
})
