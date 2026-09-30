import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RoomPreviewSection from '@/modules/rooms/components/RoomPreviewSection.vue'

const mountSection = (props: Record<string, unknown> = {}) =>
  mount(RoomPreviewSection, {
    props: {
      roomName: 'Power Generator',
      imageUrl: null,
      roomImageUrl: null,
      dwellerCapacity: 2,
      assignedDwellers: [],
      ...props,
    },
  })

describe('RoomPreviewSection scene source precedence', () => {
  it('uses the detail-scene URL when present', () => {
    const wrapper = mountSection({
      imageUrl: 'https://cdn.test/grid.png',
      roomImageUrl: 'https://cdn.test/room.png',
      detailSceneUrl: 'https://cdn.test/detail-scene.png',
    })

    expect(wrapper.get('.room-image').attributes('src')).toBe('https://cdn.test/detail-scene.png')
  })

  it('falls back to the room image URL when no detail scene is provided', () => {
    const wrapper = mountSection({
      imageUrl: 'https://cdn.test/grid.png',
      roomImageUrl: 'https://cdn.test/room.png',
    })

    expect(wrapper.get('.room-image').attributes('src')).toBe('https://cdn.test/room.png')
  })

  it('falls back to the grid image URL when neither detail scene nor room image exist', () => {
    const wrapper = mountSection({ imageUrl: 'https://cdn.test/grid.png' })

    expect(wrapper.get('.room-image').attributes('src')).toBe('https://cdn.test/grid.png')
  })

  it('renders the placeholder when no image source exists', () => {
    const wrapper = mountSection()

    expect(wrapper.find('.room-image').exists()).toBe(false)
    expect(wrapper.text()).toContain('No Image Available')
  })
})