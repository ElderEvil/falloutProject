import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerPanel from '@/modules/dwellers/components/DwellerPanel.vue'

describe('DwellerPanel', () => {
  it('puts the complete dossier action above the tab-specific controls', async () => {
    const wrapper = mount(DwellerPanel, {
      props: { dweller: { first_name: 'Amata', last_name: 'Almodovar' } as any },
      global: { stubs: { DwellerBio: true, DwellerAppearance: true, DwellerStats: true, DwellerEquipment: true, FamilyTreePanel: true } },
    })

    await wrapper.find('.dossier-action button').trigger('click')

    expect(wrapper.find('.dossier-action').text()).toContain('Complete dossier')
    expect(wrapper.emitted('generate-all')).toHaveLength(1)
  })

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
