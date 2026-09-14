import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import DwellerRoleMatch from '@/modules/dwellers/components/DwellerRoleMatch.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

beforeEach(() => {
  setActivePinia(createPinia())
})

// Agility is the highest stat, so an Agility room is the ideal match.
const base = {
  S: 4,
  P: 3,
  E: 5,
  C: 2,
  I: 6,
  A: 9,
  L: 1,
  is_adult: true,
  age_group: 'adult',
  is_dead: false,
  room: { id: 'room-1', name: 'Diner', ability: 'agility' },
} as unknown as Dweller

function mountMatch(overrides: Partial<Dweller> = {}) {
  const dweller = { ...base, ...overrides } as Dweller
  const ctx = createMockDwellerDetailContext({ dweller: ref(dweller) as never })
  return mountWithDwellerContext(DwellerRoleMatch, {
    context: ctx,
    global: { plugins: [createPinia()], stubs: { RouterLink: true } },
  } as never)
}

describe('DwellerRoleMatch', () => {
  it('marks a room that uses the dweller\'s strongest stat', () => {
    const wrapper = mountMatch()

    expect(wrapper.text()).toContain('Matched')
    expect(wrapper.find('.role-match-ok').exists()).toBe(true)
  })

  it('flags a room that does not use their strongest stat', () => {
    const wrapper = mountMatch({ room: { id: 'room-2', name: 'Power Generator', ability: 'strength' } } as never)

    expect(wrapper.text()).toContain('Mismatch')
    expect(wrapper.find('.role-match-off').exists()).toBe(true)
  })

  it('renders nothing for an unassigned dweller', () => {
    const wrapper = mountMatch({ room: null } as never)

    expect(wrapper.find('.role-match').exists()).toBe(false)
  })

  it('renders nothing for youth, whose room ability is the apprenticeship by construction', () => {
    const wrapper = mountMatch({ is_adult: false, age_group: 'teen' } as never)

    expect(wrapper.find('.role-match').exists()).toBe(false)
  })
})
