import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
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

  it('hides worker assignment actions in a read-only preview', () => {
    const wrapper = mountPreview({ assignEnabled: false })
    expect(wrapper.find('button[aria-label^="Unassign"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="Assign worker"]').exists()).toBe(false)
    expect(wrapper.get('button[aria-label="Open Ada "]').exists()).toBe(true)
    wrapper.unmount()
  })
})
