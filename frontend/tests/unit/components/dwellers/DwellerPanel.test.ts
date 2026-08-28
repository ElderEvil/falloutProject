import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerPanel from '@/modules/dwellers/components/DwellerPanel.vue'

describe('DwellerPanel', () => {
  it('updates its active tab when notification navigation changes the query tab', async () => {
    const wrapper = mount(DwellerPanel, {
      props: {
        dweller: { first_name: 'Amata', last_name: 'Almodovar' } as any,
        initialTab: 'profile',
      },
      global: {
        stubs: {
          DwellerBio: true,
          DwellerAppearance: true,
          DwellerStats: true,
          DwellerEquipment: true,
          FamilyTreePanel: true,
        },
      },
    })

    await wrapper.setProps({ initialTab: 'stats' })

    expect(wrapper.find('.utabs-button.active').text()).toBe('Stats')
  })
})
