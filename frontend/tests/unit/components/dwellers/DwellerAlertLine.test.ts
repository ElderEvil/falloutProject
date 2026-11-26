import { describe, it, expect } from 'vite-plus/test'
import { ref } from 'vue'
import DwellerAlertLine from '@/modules/dwellers/components/DwellerAlertLine.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

const healthyAdult = {
  is_dead: false,
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
  it.each([
    ['a healthy dweller with a room', {}],
    ['a lightly damaged dweller', { health: 70 }],
    ['a deceased dweller', { is_dead: true, health: 0, room: null }],
  ] as const)('renders nothing for %s', (_name, overrides) => {
    const wrapper = mountAlertLine(overrides as Partial<Dweller>)

    expect(wrapper.findAll('.alert-chip')).toHaveLength(0)
  })

  it.each([
    ['severe injury below half of max health', { health: 30, radiation: 20 }, '30/80 HP'],
    // 35/100 HP with 40 radiation: effective max 60, so 35 sits above 60/2 and the
    // radiation-reduced threshold missed it; the absolute half rule catches it.
    [
      'a damaged, heavily-irradiated dweller the effective ceiling would hide',
      { health: 35, radiation: 40 },
      '35/60 HP',
    ],
  ])('flags %s', (_name, overrides, hp) => {
    const wrapper = mountAlertLine(overrides as Partial<Dweller>)

    expect(wrapper.text()).toContain('Injured')
    expect(wrapper.text()).toContain(hp)
  })

  it('flags radiation', () => {
    const wrapper = mountAlertLine({ radiation: 30 })

    expect(wrapper.text()).toContain('Radiated — 30')
  })

  it('flags low happiness', () => {
    const wrapper = mountAlertLine({ happiness: 30 })

    expect(wrapper.text()).toContain('Unhappy — 30%')
  })

  it.each(['adult', 'child'])(
    'flags an unassigned %s dweller with a single short label',
    (age_group) => {
      const wrapper = mountAlertLine({ room: null, status: 'idle', age_group } as Partial<Dweller>)

      expect(wrapper.findAll('.alert-chip')).toHaveLength(1)
      expect(wrapper.get('.alert-chip').text()).toBe('Unassigned')
    }
  )
})
