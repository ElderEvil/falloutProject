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

    expect(wrapper.find('.utabs-button.active').text()).toBe('Stats')
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
    expect(wrapper.find('.utabs-button.active').text()).toBe('Profile')
  })
})
