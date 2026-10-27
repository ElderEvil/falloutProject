import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import ExpeditionRoomStepper from '@/modules/exploration/components/ExpeditionRoomStepper.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

describe('ExpeditionRoomStepper', () => {
  it('marks completed, current, and upcoming rooms', () => {
    const wrapper = mount(ExpeditionRoomStepper, {
      props: {
        rooms: ['Parking Lot', 'Collapsed Aisles', 'Storage Room', 'Prize Stock'],
        current: 1,
      },
    })

    const steps = wrapper.findAll('li')
    expect(steps).toHaveLength(4)
    expect(steps[0]!.text()).toContain('Parking Lot')
    expect(steps[0]!.find('[aria-current="step"]').exists()).toBe(false)
    expect(steps[1]!.find('[aria-current="step"]').exists()).toBe(true)
    expect(steps[2]!.text()).toContain('Storage Room')
  })

  it('marks every room complete for a cleared run', () => {
    const wrapper = mount(ExpeditionRoomStepper, {
      props: {
        rooms: ['Parking Lot', 'Collapsed Aisles'],
        current: 1,
        status: 'cleared',
      },
    })

    const steps = wrapper.findAll('li')
    expect(steps[1]!.find('[aria-current="step"]').exists()).toBe(false)
    expect(steps[1]!.find('[data-icon="mdi:check"]').exists()).toBe(true)
  })
})
