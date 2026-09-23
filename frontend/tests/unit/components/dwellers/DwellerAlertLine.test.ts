import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import DwellerAlertLine from '@/modules/dwellers/components/DwellerAlertLine.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

const healthyAdult = {
  is_dead: false,
  is_adult: true,
  age_group: 'adult',
  max_health: 100,
  health: 100,
  radiation: 0,
  happiness: 75,
  status: 'working',
  room: { id: 'room-1', name: 'Power Generator' },
} as unknown as Dweller

function mountAlertLine(overrides: Partial<Dweller> = {}) {
  const dweller = { ...healthyAdult, ...overrides } as Dweller
  const ctx = createMockDwellerDetailContext({ dweller: ref(dweller) as never })
  return mountWithDwellerContext(DwellerAlertLine, { context: ctx })
}

describe('DwellerAlertLine', () => {
  it('renders nothing for a healthy dweller with a room', () => {
    const wrapper = mountAlertLine()

    expect(wrapper.findAll('.alert-chip')).toHaveLength(0)
  })

  it('flags injury against the radiation-reduced ceiling', () => {
    const wrapper = mountAlertLine({ health: 40, radiation: 20 })

    const text = wrapper.text()
    expect(text).toContain('Injured')
    expect(text).toContain('40/80 HP')
  })

  it('flags radiation', () => {
    const wrapper = mountAlertLine({ radiation: 30 })

    expect(wrapper.text()).toContain('Radiated — 30')
  })

  it('flags low happiness', () => {
    const wrapper = mountAlertLine({ happiness: 30 })

    expect(wrapper.text()).toContain('Unhappy — 30%')
  })

  it('flags an unassigned dweller with a single short label', () => {
    const adult = mountAlertLine({ room: null, status: 'idle' })
    expect(adult.find('.alert-chip').text()).toBe('Unassigned')

    const youth = mountAlertLine({ room: null, status: 'idle', is_adult: false, age_group: 'child' })
    expect(youth.find('.alert-chip').text()).toBe('Unassigned')
  })

  it('stays silent for a deceased dweller', () => {
    const wrapper = mountAlertLine({ is_dead: true, health: 0, room: null })

    expect(wrapper.findAll('.alert-chip')).toHaveLength(0)
  })
})
