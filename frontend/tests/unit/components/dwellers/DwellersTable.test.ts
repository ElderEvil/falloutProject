import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellersTable from '@/modules/dwellers/components/table/DwellersTable.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { DwellerTableColumnId } from '@/modules/dwellers/models/dwellerTable'
import type { Room } from '@/modules/rooms/models/room'

function makeDweller(overrides: Partial<DwellerShort> = {}): DwellerShort {
  return {
    id: 'dweller-1',
    first_name: 'Sarah',
    last_name: 'Lyons',
    thumbnail_url: null,
    level: 5,
    health: 80,
    max_health: 100,
    radiation: 0,
    happiness: 75,
    room_id: 'room-1',
    status: 'working',
    is_adult: true,
    age_group: 'adult',
    gender: 'female',
    rarity: 'rare',
    strength: 8,
    perception: 4,
    endurance: 4,
    charisma: 4,
    intelligence: 4,
    agility: 4,
    luck: 4,
    ...overrides,
  }
}

const rooms = [
  { id: 'room-1', name: 'Arena', category: 'arena', ability: 'strength' } as Room,
]

function mountTable(columns: DwellerTableColumnId[], dwellers = [makeDweller()], isLoading = false) {
  return mount(DwellersTable, {
    props: { dwellers, rooms, columns, isLoading },
    global: { stubs: { Icon: true } },
  })
}

describe('DwellersTable', () => {
  describe('Columns', () => {
    it('renders only the enabled columns, in catalog order', () => {
      const wrapper = mountTable(['room', 'name', 'level'])

      const headers = wrapper.findAll('thead th').map((th) => th.text())
      expect(headers).toEqual(['Name', 'Level', 'Room'])
    })

    it('renders a portrait cell for the portrait column', () => {
      const wrapper = mountTable(['portrait', 'name'])
      expect(wrapper.findAll('tbody td')).toHaveLength(2)
    })
  })

  describe('Dweller data', () => {
    it('renders identity, progression, vitals, status and room values', () => {
      const wrapper = mountTable([
        'name',
        'level',
        'status',
        'health',
        'happiness',
        'room',
      ])

      const cells = wrapper.findAll('tbody td').map((td) => td.text())
      expect(cells).toEqual(['Sarah Lyons', '5', 'Working', '80 / 100', '75%', 'Arena'])
    })

    it('shows Unassigned when the dweller has no room', () => {
      const wrapper = mountTable(['room'], [makeDweller({ room_id: null })])
      expect(wrapper.find('tbody').text()).toContain('Unassigned')
    })
  })

  describe('Emits', () => {
    it('emits view-details when a row is activated', async () => {
      const wrapper = mountTable(['name'])

      await wrapper.find('tbody tr').trigger('click')

      expect(wrapper.emitted('view-details')?.[0]).toEqual(['dweller-1'])
    })

    it('emits open-room from the room cell without activating the row', async () => {
      const wrapper = mountTable(['room'])

      await wrapper.find('tbody td button').trigger('click')

      expect(wrapper.emitted('open-room')?.[0]).toEqual(['room-1'])
      expect(wrapper.emitted('view-details')).toBeUndefined()
    })
  })

  describe('States', () => {
    it('renders loading skeleton rows', () => {
      const wrapper = mountTable(['name', 'level'], [], true)
      expect(wrapper.findAll('tbody tr')).toHaveLength(5)
    })

    it('renders an empty message when there are no dwellers', () => {
      const wrapper = mountTable(['name'], [], false)
      expect(wrapper.find('tbody').text()).toContain('No dwellers to show')
    })
  })
})
