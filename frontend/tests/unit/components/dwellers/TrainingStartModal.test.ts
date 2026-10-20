import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import TrainingStartModal from '@/modules/dwellers/components/modals/TrainingStartModal.vue'
import { useRoomStore } from '@/modules/rooms/stores/room'

describe('TrainingStartModal maturity', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it.each(['child', 'teen', 'adult', 'elder'] as const)(
    'gates training for %s',
    async (age_group) => {
      useRoomStore().rooms = [{ id: 'room-1', category: 'training', ability: 'strength' }] as never
      const wrapper = mount(TrainingStartModal, {
        props: {
          modelValue: true,
          dweller: { id: 'dweller-1', first_name: 'Amata', age_group, S: 5 } as never,
        },
        global: { stubs: { TerminalModal: { template: '<div><slot /></div>' } } },
      })
      const stat = wrapper.get('button.stat-button')
      const start = wrapper.findAll('button').find((button) => button.text() === 'Start Training')!
      if (['child', 'teen'].includes(age_group)) {
        expect(stat.attributes('disabled')).toBeDefined()
        expect(start.attributes('disabled')).toBeDefined()
        expect(wrapper.text()).toContain('Training unlocks at adulthood')
      } else {
        expect(stat.attributes('disabled')).toBeUndefined()
        await stat.trigger('click')
        expect(start.attributes('disabled')).toBeUndefined()
      }
    }
  )
})
