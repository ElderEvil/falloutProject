import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TrainingRoomCard from '@/modules/progression/components/training/TrainingRoomCard.vue'
import type { Room } from '@/modules/rooms/models/room'

const room = {
  id: 'weight-room-1',
  name: 'Weight Room',
  category: 'training',
  ability: 'strength',
  tier: 1,
  size: 3,
  size_min: 3,
  image_url: null,
} as Room

describe('TrainingRoomCard', () => {
  it('renders primary terminal occupancy slots for each available training place', () => {
    const wrapper = mount(TrainingRoomCard, {
      props: { room, activeCount: 1 },
      global: { stubs: { Icon: true, UProgressBar: true } },
    })

    expect(wrapper.findAll('.occupancy-slot')).toHaveLength(2)
    expect(wrapper.findAll('.occupancy-slot--filled')).toHaveLength(1)
    expect(wrapper.text()).toContain('1 / 2')
  })

  it('keeps the full room name, tier and occupancy in the compact card', () => {
    const intelligenceRoom = {
      ...room,
      id: 'intelligence-room-1',
      name: 'Classroom',
      ability: 'intelligence',
    } as Room

    const wrapper = mount(TrainingRoomCard, {
      props: { room: intelligenceRoom, activeCount: 0 },
      global: { stubs: { Icon: true, UProgressBar: true } },
    })

    expect(wrapper.get('[title="Classroom"]').text()).toBe('Classroom')
    expect(wrapper.text()).toContain('T1')
    expect(wrapper.text()).toContain('0 / 2')
  })
})
