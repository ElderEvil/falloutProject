import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vite-plus/test'
import RoomPreviewSection from '@/modules/rooms/components/RoomPreviewSection.vue'

const dweller = (id: string, name: string) => ({
  id,
  first_name: name,
  last_name: '',
  thumbnail_url: null as string | null,
})

const baseProps = {
  roomName: 'Power Generator',
  imageUrl: null as string | null,
  roomImageUrl: null as string | null,
  dwellerCapacity: 2,
  assignedDwellers: [dweller('d1', 'Ada')],
  showApprenticeSlot: false,
  assignEnabled: true,
}

const mountPreview = (props: Record<string, unknown> = {}) =>
  mount(RoomPreviewSection, {
    props: { ...baseProps, ...props },
  })

describe('RoomPreviewSection unassign affordance (issue #1083)', () => {
  it('emits the worker ID when unassign is activated', async () => {
    const wrapper = mountPreview()
    const button = wrapper.get('button[aria-label="Unassign Ada "]')
    await button.trigger('click')
    expect(wrapper.emitted('unassign')).toEqual([['d1']])
    expect(wrapper.emitted('activate')).toBeUndefined()
    wrapper.unmount()
  })

  it('emits the apprentice ID when unassign is activated', async () => {
    const wrapper = mountPreview({
      showApprenticeSlot: true,
      assignedDwellers: [{ ...dweller('a1', 'Ash'), apprentice_stat: 'strength' }],
    })
    await wrapper.get('button[aria-label="Unassign Ash "]').trigger('click')
    expect(wrapper.emitted('unassign')).toEqual([['a1']])
    expect(wrapper.emitted('activate')).toBeUndefined()
    wrapper.unmount()
  })

  it('orders workers before the dedicated apprentice slot', () => {
    const wrapper = mountPreview({
      showApprenticeSlot: true,
      dwellerCapacity: 2,
      assignedDwellers: [
        { ...dweller('a1', 'Ash'), apprentice_stat: 'strength' },
        dweller('d1', 'Ada'),
      ],
    })

    const openLabels = wrapper
      .findAll('button[aria-label^="Open"]')
      .map((button) => button.attributes('aria-label'))
    expect(openLabels).toEqual(['Open Ada ', 'Open Ash '])
    expect(wrapper.find('.apprentice-ribbon').exists()).toBe(false)
    expect(wrapper.get('.apprentice-marker').text()).toContain('S')
    expect(wrapper.get('.apprentice-marker').attributes('aria-label')).toContain('strength')
    expect(wrapper.get('.apprentice-slot').attributes('class')).toContain('slot-filled')
    wrapper.unmount()
  })

  it('renders visible silhouette placeholders for empty worker and apprentice slots', () => {
    const wrapper = mountPreview({
      showApprenticeSlot: true,
      dwellerCapacity: 1,
      assignedDwellers: [],
    })

    const workerSilhouette = wrapper.get('.scene-empty-worker .empty-dweller-silhouette')
    expect(wrapper.get('.dweller-sprites-overlay').attributes('style')).toContain(
      'FOS_Dw_Default_Human_Male.webp'
    )
    expect(workerSilhouette.element.tagName).toBe('SPAN')
    expect(wrapper.get('.scene-empty-worker .empty-dweller-plus').exists()).toBe(true)
    expect(
      wrapper.get('.scene-empty-apprentice .empty-dweller-silhouette').attributes('class')
    ).toContain('empty-dweller-silhouette--apprentice')
    expect(
      wrapper.get('.scene-empty-apprentice .empty-dweller-silhouette').attributes('style')
    ).toContain('FOS_Dw_Default_Human_Teen_Male_SkinBrown_HairBrown.webp')
    wrapper.unmount()
  })

  it('fits assigned portraits inside the slot without the card zoom', () => {
    const wrapper = mountPreview({
      dwellerCapacity: 1,
      assignedDwellers: [
        {
          ...dweller('d1', 'Ada'),
          thumbnail_url: '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp',
        },
      ],
    })

    const button = wrapper.get('button[aria-label="Open Ada "]')
    expect(button.find('.portrait-clip-all').exists()).toBe(true)
    expect(button.get('img').attributes('class')).not.toContain('default-portrait-zoom')
    wrapper.unmount()
  })

  it('hides worker assignment actions in a read-only preview', () => {
    const wrapper = mountPreview({ assignEnabled: false })
    expect(wrapper.find('button[aria-label^="Unassign"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Assign worker"]').exists()).toBe(false)
    expect(wrapper.find('.empty-dweller-plus').exists()).toBe(false)
    expect(wrapper.get('button[aria-label="Open Ada "]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('labels workers and the apprentice above their portraits', () => {
    const wrapper = mountPreview({
      showApprenticeSlot: true,
      dwellerCapacity: 1,
      assignedDwellers: [
        { ...dweller('d1', 'Ada'), last_name: 'Lovelace' },
        { ...dweller('a1', 'Ash'), apprentice_stat: 'strength' },
      ],
    })

    expect(wrapper.findAll('.scene-dweller-name').map((node) => node.text())).toEqual([
      'Ada',
      'Ash',
    ])
    expect(wrapper.get('.scene-dweller-name').attributes('title')).toBe('Ada Lovelace')
    wrapper.unmount()
  })

  it('scales portraits by age and race like the arena', () => {
    const wrapper = mountPreview({
      dwellerCapacity: 3,
      assignedDwellers: [
        { ...dweller('adult', 'Ann'), age_group: 'adult' },
        { ...dweller('child', 'Cal'), age_group: 'child' },
        { ...dweller('mutant', 'Max'), visual_attributes: { race: 'super_mutant' } },
      ],
    })

    const styles = wrapper.findAll('.scene-dweller').map((node) => node.attributes('style'))
    expect(styles[0]).toContain('--dweller-body-scale: 1')
    expect(styles[1]).toContain('--dweller-body-scale: 0.8')
    expect(styles[2]).toContain('--dweller-body-scale: 1.18')
    wrapper.unmount()
  })
})
