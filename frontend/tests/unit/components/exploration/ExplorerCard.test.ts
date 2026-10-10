import { afterEach, describe, expect, it, vi, beforeEach } from 'vitest'
import { createIconifyMock, createRouterMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { Progress } from '@/core/components/ui/progress'
import ExplorerCard from '@/modules/exploration/components/ExplorerCard.vue'
import ExplorerActions from '@/modules/exploration/components/ExplorerActions.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
  getIdentityOptions: vi
    .fn()
    .mockResolvedValue({ races: [], factions_by_race: {}, states_by_race: {} }),
}))

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock" />' }))

const exploration = {
  id: 'exploration-1',
  vault_id: 'vault-1',
  dweller_id: 'dweller-1',
  status: 'active',
  duration: 8,
  start_time: '2026-01-01T00:00:00Z',
  end_time: null,
  events: [],
  loot_collected: [],
  total_distance: 0,
  total_caps_found: 0,
  enemies_encountered: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  dweller_strength: 1,
  dweller_perception: 1,
  dweller_endurance: 1,
  dweller_charisma: 1,
  dweller_intelligence: 1,
  dweller_agility: 1,
  dweller_luck: 1,
  stimpaks: 0,
  radaways: 0,
} as Exploration

const dweller = {
  first_name: 'Lucy',
  last_name: 'MacLean',
  image_url: 'example.com/lucy.png',
  thumbnail_url: 'example.com/lucy-thumb.png',
} as Dweller

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('ExplorerCard', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the exploring dweller portrait', () => {
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.find('.dweller-portrait').attributes('src')).toBe(
      'http://example.com/lucy-thumb.png'
    )
    expect(wrapper.find('.dweller-portrait').attributes('alt')).toBe('Lucy MacLean portrait')

    wrapper.unmount()
  })

  it('uses the thumbnail when image_url is blank', () => {
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration,
        dweller: { ...dweller, image_url: '', thumbnail_url: 'example.com/thumb.png' },
      },
    })

    expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('http://example.com/thumb.png')
  })

  it('renders mission metrics and the equipped weapon and outfit', () => {
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration: {
          ...exploration,
          loot_collected: [{ name: 'Loot' }],
          total_caps_found: 12,
        },
        dweller: {
          ...dweller,
          weapon: { name: 'Experimental Plasma Rifle' },
          outfit: { name: 'Vault Suit' },
        },
      },
    })

    expect(wrapper.text()).toContain('Distance')
    expect(wrapper.text()).toContain('Experimental Plasma Rifle')
    expect(wrapper.text()).toContain('Vault Suit')
  })

  it('updates progress and remaining time while mounted, then stops its clock when unmounted', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T01:00:00Z'))
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.findComponent(Progress).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.find('.progress-percentage').text()).toBe('13%')
    expect(wrapper.find('.progress-time').text()).toBe('7h 0m remaining')
    expect(vi.getTimerCount()).toBe(1)

    await vi.advanceTimersByTimeAsync(60 * 60 * 1000)
    await nextTick()

    expect(wrapper.find('.progress-percentage').text()).toBe('25%')
    expect(wrapper.find('.progress-time').text()).toBe('6h 0m remaining')

    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('preserves timezone offsets in exploration start times', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T05:00:00Z'))
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration: { ...exploration, start_time: '2026-01-01T00:00:00-05:00' },
        dweller,
      },
    })

    expect(wrapper.find('.progress-percentage').text()).toBe('0%')

    wrapper.unmount()
  })

  it('uses compact shared actions to complete or recall the explorer', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T09:00:00Z'))
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    const actions = wrapper.findComponent(ExplorerActions)
    expect(actions.props('compact')).toBe(true)
    expect(actions.findAll('button')).toHaveLength(2)

    await actions.findAll('button')[0].trigger('click')
    await actions.findAll('button')[1].trigger('click')

    expect(wrapper.emitted('complete')).toEqual([['exploration-1']])
    expect(wrapper.emitted('recall')).toEqual([['exploration-1']])
  })

  it('links dispatched explorers to their map marker', () => {
    const wrapper = mount(ExplorerCard, {
      props: { exploration: { ...exploration, target_location_id: 'loc-9' }, dweller },
    })

    expect(wrapper.find('.view-on-map').attributes('href')).toBe('/vault/vault-1/map?place=loc-9')
  })

  it('links free-roam explorers to the plain map', () => {
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller } })

    expect(wrapper.find('.view-on-map').attributes('href')).toBe('/vault/vault-1/map')
  })

  it('renders the whole dispatch party as compact quest-style member rows', () => {
    const partyMembers = [
      companion('dweller-1', 'Lucy'),
      companion('dweller-2', 'Carla'),
      companion('dweller-3', 'Bea'),
    ]
    const wrapper = mount(ExplorerCard, { props: { exploration, dweller, partyMembers } })

    expect(wrapper.find('.dweller-info').exists()).toBe(false)
    expect(wrapper.find('.equipment-section').exists()).toBe(false)
    expect(wrapper.text()).toContain('Expedition party')
    expect(wrapper.findAll('.party-member')).toHaveLength(3)
    expect(wrapper.findAll('.member-name').map((node) => node.text())).toEqual([
      'Lucy Vault',
      'Carla Vault',
      'Bea Vault',
    ])
  })

  it('keeps a dispatched solo party compact while its roster loads', () => {
    const wrapper = mount(ExplorerCard, {
      props: {
        exploration: {
          ...exploration,
          target_location_id: 'site-1',
          events: [{ description: 'Old activity' }],
        },
        dweller,
      },
    })
    expect(wrapper.find('.dweller-info').exists()).toBe(false)
    expect(wrapper.find('.recent-events').exists()).toBe(false)
    expect(wrapper.findAll('.member-name').map((node) => node.text())).toEqual(['Lucy MacLean'])
    expect(wrapper.findComponent(ExplorerActions).props('compact')).toBe(true)
  })

  it('renders no companion row for a solo run', () => {
    const wrapper = mount(ExplorerCard, {
      props: { exploration, dweller, partyMembers: [companion('dweller-1', 'Lucy')] },
    })

    expect(wrapper.find('.party-section').exists()).toBe(false)
  })
})

function companion(id: string, firstName: string): DwellerShort {
  return {
    id,
    first_name: firstName,
    last_name: 'Vault',
    level: 3,
    thumbnail_url: `example.com/${id}.png`,
    age_group: 'adult',
    gender: 'female',
    rarity: 'common',
  } as DwellerShort
}
