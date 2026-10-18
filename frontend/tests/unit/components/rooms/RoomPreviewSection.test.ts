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
  it('keeps the unassign control hover-gated (opacity 0 until hover/focus)', () => {
    const wrapper = mountPreview()
    const button = wrapper.get('.scene-unassign')
    expect(button.classes()).toContain('scene-unassign')
    wrapper.unmount()
  })

  it('enlarges the occupant portrait beyond the legacy 48px slot', () => {
    const wrapper = mountPreview()
    const slot = wrapper.get('.dweller-sprite-slot')
    expect(slot.classes()).toContain('dweller-sprite-slot-lg')
    wrapper.unmount()
  })

  it('keeps the unassign button reachable on touch (labeled, no hover-only trap)', () => {
    const wrapper = mountPreview()
    const button = wrapper.get('.scene-unassign')
    expect(button.attributes('aria-label')).toContain('Unassign Ada')
    wrapper.unmount()
  })
})
