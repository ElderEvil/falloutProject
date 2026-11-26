import { describe, expect, it } from 'vite-plus/test'
import { nextTick, ref } from 'vue'
import DwellerPanel from '@/modules/dwellers/components/DwellerPanel.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'

const stubs = {
  DwellerBio: true,
  DwellerAppearance: true,
  DwellerStats: true,
  DwellerEquipment: true,
  FamilyTreePanel: true,
}

describe('DwellerPanel', () => {
  const mountPanel = (initialTab?: string) => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ first_name: 'Amata', last_name: 'Almodovar' }) as never,
      initialTab: ref(initialTab) as never,
    })
    const wrapper = mountWithDwellerContext(DwellerPanel, {
      context: ctx,
      global: { stubs },
    })
    return { wrapper, ctx }
  }

  it('updates its active tab when notification navigation changes the query tab', async () => {
    const { wrapper, ctx } = mountPanel('profile')

    ctx.initialTab.value = 'stats'
    await nextTick()

    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('SPECIAL')
  })

  it('falls back to Profile when the initial tab is unknown', async () => {
    const { wrapper } = mountPanel('does-not-exist')

    await nextTick()

    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toBe('Profile')
  })

  it('renders the active section in a linked tabpanel', async () => {
    const { wrapper } = mountPanel('profile')

    await nextTick()

    const panel = wrapper.find('[role="tabpanel"]')
    expect(panel.exists()).toBe(true)
    expect(wrapper.find('[role="tab"][aria-selected="true"]').attributes('aria-controls')).toBe(
      panel.attributes('id')
    )
  })
})
