import { describe, expect, it } from 'vitest'
import { nextTick, ref } from 'vue'
import DwellerPanel from '@/modules/dwellers/components/DwellerPanel.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../helpers/dwellerDetailContext'

describe('DwellerPanel', () => {
  const stubs = {
    DwellerBio: true,
    DwellerAppearance: true,
    DwellerStats: true,
    DwellerEquipment: true,
    FamilyTreePanel: true,
  }


  it('updates its active tab when notification navigation changes the query tab', async () => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ first_name: 'Amata', last_name: 'Almodovar' }) as never,
      initialTab: ref('profile') as never,
    })
    const wrapper = mountWithDwellerContext(DwellerPanel, {
      context: ctx,
      global: { stubs },
    })

    ctx.initialTab.value = 'stats'
    await nextTick()

    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('SPECIAL')
  })

  it('falls back to Profile when the initial tab is unknown', async () => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ first_name: 'Amata', last_name: 'Almodovar' }) as never,
      initialTab: ref('does-not-exist') as never,
    })
    const wrapper = mountWithDwellerContext(DwellerPanel, {
      context: ctx,
      global: { stubs },
    })

    await nextTick()
    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('Profile')
  })

  it('renders the active section in a linked tabpanel', async () => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ first_name: 'Amata', last_name: 'Almodovar' }) as never,
      initialTab: ref('profile') as never,
    })
    const wrapper = mountWithDwellerContext(DwellerPanel, {
      context: ctx,
      global: { stubs },
    })

    await nextTick()
    const panel = wrapper.find('[role="tabpanel"]')
    expect(panel.exists()).toBe(true)

    const activeTab = wrapper.find('[role="tab"][aria-selected="true"]')
    expect(activeTab.attributes('aria-controls')).toBe(panel.attributes('id'))
  })
})
