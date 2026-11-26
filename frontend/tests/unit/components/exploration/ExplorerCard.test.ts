import { afterEach, describe, expect, it, vi, beforeEach } from 'vite-plus/test'
import { createIconifyMock, createRouterMock } from '../../helpers/mocks'
import { createExploration } from '../../helpers/explorationFixtures'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { Progress } from '@/core/components/ui/progress'
import ExplorerCard from '@/modules/exploration/components/ExplorerCard.vue'
import ExplorerActions from '@/modules/exploration/components/ExplorerActions.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import { fromExplorationShort } from '@/modules/exploration/stores/exploration'
import type { ExplorationReadShort } from '@/modules/exploration/api/exploration'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-1' } }))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
  getIdentityOptions: vi
    .fn()
    .mockResolvedValue({ races: [], factions_by_race: {}, states_by_race: {} }),
}))

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock" />' }))

enableAutoUnmount(afterEach)

const exploration = createExploration()

const dweller = {
  first_name: 'Lucy',
  last_name: 'MacLean',
  image_url: 'example.com/lucy.png',
  thumbnail_url: 'example.com/lucy-thumb.png',
} as Dweller

/** The card reads one run: override the run's fields, or the props themselves. */
const mountCard = (run: Partial<Exploration> = {}, props: Record<string, unknown> = {}) =>
  mount(ExplorerCard, {
    props: { exploration: { ...exploration, ...run }, dweller, ...props },
  })

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('ExplorerCard', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the exploring dweller portrait', () => {
    const portrait = mountCard().find('.dweller-portrait')

    expect(portrait.attributes('src')).toBe('http://example.com/lucy-thumb.png')
    expect(portrait.attributes('alt')).toBe('Lucy MacLean portrait')
  })

  it('uses the thumbnail when image_url is blank', () => {
    const blank = { ...dweller, image_url: '', thumbnail_url: 'example.com/thumb.png' }

    expect(mountCard({}, { dweller: blank }).find('.dweller-portrait').attributes('src')).toBe(
      'http://example.com/thumb.png'
    )
  })

  it('renders mission metrics and the equipped weapon and outfit', () => {
    const wrapper = mountCard(
      { loot_collected: [{ name: 'Loot' }], total_caps_found: 12 },
      {
        dweller: {
          ...dweller,
          weapon: { name: 'Experimental Plasma Rifle' },
          outfit: { name: 'Vault Suit' },
        },
      }
    )

    expect(wrapper.text()).toContain('Distance')
    expect(wrapper.text()).toContain('Experimental Plasma Rifle')
    expect(wrapper.text()).toContain('Vault Suit')
  })

  it('updates progress and remaining time while mounted, then stops its clock when unmounted', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T01:00:00Z'))
    const wrapper = mountCard()

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
    const wrapper = mountCard({ start_time: '2026-01-01T00:00:00-05:00' })

    expect(wrapper.find('.progress-percentage').text()).toBe('0%')
  })

  it('uses compact shared actions to complete or recall the explorer', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T09:00:00Z'))
    const wrapper = mountCard()

    const actions = wrapper.findComponent(ExplorerActions)
    expect(actions.props('compact')).toBe(true)
    expect(actions.findAll('button')).toHaveLength(2)

    await actions.findAll('button')[0].trigger('click')
    await actions.findAll('button')[1].trigger('click')

    expect(wrapper.emitted('complete')).toEqual([['exploration-1']])
    expect(wrapper.emitted('recall')).toEqual([['exploration-1']])
  })

  it.each([
    [
      'a dispatch run',
      { target_location_id: 'loc-9', carry_capacity: 21, pack_slots_used: 3 },
      '3 / 21',
    ],
    ['a free roam', { carry_capacity: 25, pack_slots_used: 4 }, '4 / 25'],
  ])('renders the pack capacity strip beside the mission stats on %s', (_, run, count) => {
    // Dispatch runs are the common case; capacity comes from the run's snapshot Strength, so the
    // strip belongs on them too. Hiding it there once made the pack invisible for most expeditions.
    const wrapper = mountCard(run)

    expect(wrapper.find('.pack-strip').exists()).toBe(true)
    expect(wrapper.find('.pack-count').text()).toBe(count)
  })

  it.each([
    ['a dispatched explorer', { target_location_id: 'loc-9' }, '/vault/vault-1/map?place=loc-9'],
    ['a free-roam explorer', {}, '/vault/vault-1/map'],
  ])('links %s to its map marker', (_, run, href) => {
    expect(mountCard(run).find('.view-on-map').attributes('href')).toBe(href)
  })

  /** List-payload loot row: the list endpoint serves items without the detail-only fields. */
  const loot = (item_name: string, item_type: string, quantity: number) => ({
    item_name,
    quantity,
    rarity: 'Common',
    item_type,
    found_at: '2026-01-01T00:10:00Z',
  })

  it('renders pack, item count and recent activity from the real list payload', () => {
    // The explorer list serves ExplorationReadShort. Reading it through the detail-only fields
    // used to show "0 / 15", no item count and no activity; keep this fixture on the list shape.
    const listRow: ExplorationReadShort = {
      id: 'exploration-1',
      vault_id: 'vault-1',
      dweller_id: 'dweller-1',
      status: 'active',
      start_time: '2026-01-01T00:00:00Z',
      end_time: null,
      return_started_at: null,
      return_completes_at: null,
      duration: 8,
      events: [
        {
          type: 'loot',
          description: 'Found a desk fan',
          timestamp: '2026-01-01T00:10:00Z',
          time_elapsed_hours: 0.5,
        },
      ],
      loot_collected: [loot('Desk Fan', 'junk', 2), loot('Stimpak', 'stimpak', 1)],
      total_distance: 6,
      total_caps_found: 30,
      enemies_encountered: 1,
      stimpaks: 2,
      radaways: 0,
      dweller_strength: 3,
      carry_capacity: 21,
      pack_slots_used: 2,
    }

    const wrapper = mountCard({}, { exploration: fromExplorationShort(listRow) })

    expect(wrapper.find('.pack-count').text()).toBe('2 / 21')
    const itemsMetric = wrapper
      .findAll('.terminal-metric')
      .find((metric) => metric.text().includes('Items'))
    expect(itemsMetric?.text()).toContain('2')
    expect(wrapper.find('.recent-events').text()).toContain('Found a desk fan')
  })

  it('renders the whole dispatch party as compact quest-style member rows', () => {
    const wrapper = mountCard(
      {},
      {
        partyMembers: [
          companion('dweller-1', 'Lucy'),
          companion('dweller-2', 'Carla'),
          companion('dweller-3', 'Bea'),
        ],
      }
    )

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
    const wrapper = mountCard({
      target_location_id: 'site-1',
      events: [{ description: 'Old activity' }],
    })

    expect(wrapper.find('.dweller-info').exists()).toBe(false)
    expect(wrapper.find('.recent-events').exists()).toBe(false)
    expect(wrapper.findAll('.member-name').map((node) => node.text())).toEqual(['Lucy MacLean'])
    expect(wrapper.findComponent(ExplorerActions).props('compact')).toBe(true)
  })

  it('renders no companion row for a solo run', () => {
    expect(
      mountCard({}, { partyMembers: [companion('dweller-1', 'Lucy')] })
        .find('.party-section')
        .exists()
    ).toBe(false)
  })

  it('links the dweller identity to the dweller page and the label to the expedition', () => {
    expect(
      mountCard()
        .findAllComponents({ name: 'RouterLink' })
        .map((link) => link.props('to'))
    ).toEqual([
      '/vault/vault-1/dwellers/dweller-1',
      '/vault/vault-1/dwellers/dweller-1',
      '/vault/vault-1/exploration/exploration-1',
    ])
  })

  it('links each party member to their own dweller page', () => {
    const wrapper = mountCard(
      {},
      { partyMembers: [companion('dweller-1', 'Lucy'), companion('dweller-2', 'Carla')] }
    )

    expect(wrapper.findAllComponents('.party-member').map((member) => member.props('to'))).toEqual([
      '/vault/vault-1/dwellers/dweller-1',
      '/vault/vault-1/dwellers/dweller-2',
    ])
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
