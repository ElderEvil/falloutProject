import { describe, expect, it } from 'vite-plus/test'

import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
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

async function mountRoomCard(room: Room, activeCount: number) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
  })
  await router.push('/vault/vault-1')
  const wrapper = mount(TrainingRoomCard, {
    props: { room, activeCount, vaultId: 'vault-1' },
    global: { plugins: [router], stubs: { Icon: true } },
  })
  return { wrapper, router }
}

describe('TrainingRoomCard', () => {
  it('renders primary terminal occupancy slots for each available training place', async () => {
    const { wrapper } = await mountRoomCard(room, 1)

    expect(wrapper.findAll('.occupancy-slot')).toHaveLength(2)
    expect(wrapper.findAll('.occupancy-slot--filled')).toHaveLength(1)
    expect(wrapper.text()).toContain('1 / 2')
  })

  it('opens the exact room and keeps the name, tier and occupancy', async () => {
    const intelligenceRoom = {
      ...room,
      id: 'intelligence-room-1',
      name: 'Classroom',
      ability: 'intelligence',
    } as Room

    const { wrapper, router } = await mountRoomCard(intelligenceRoom, 0)

    const link = wrapper.get('a[aria-label="Open Classroom"]')
    expect(link.attributes('href')).toBe('/vault/vault-1?roomId=intelligence-room-1')
    expect(wrapper.find('[title]').exists()).toBe(false)
    await link.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.roomId).toBe('intelligence-room-1')
    expect(wrapper.text()).toContain('T1')
    expect(wrapper.text()).toContain('0 / 2')
  })
})
