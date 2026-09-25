import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Dialog } from '@/core/components/ui/dialog'
import ExpeditionSiteModal from '@/modules/exploration/components/ExpeditionSiteModal.vue'
import { useExpeditionSiteStore } from '@/modules/exploration/stores/expeditionSite'
import type { AvailableSiteView, SiteRoomView } from '@/modules/exploration/api/expeditionSite'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const { mockList, mockEnter, mockResolve, mockRetreat } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockEnter: vi.fn(),
  mockResolve: vi.fn(),
  mockRetreat: vi.fn(),
}))

vi.mock('@/modules/exploration/api/expeditionSite', () => ({
  expeditionSiteApi: {
    listAvailableSites: (...args: unknown[]) => mockList(...args),
    enterSite: (...args: unknown[]) => mockEnter(...args),
    resolveNode: (...args: unknown[]) => mockResolve(...args),
    retreatSite: (...args: unknown[]) => mockRetreat(...args),
    getCurrentRoom: () => Promise.resolve(null),
  },
}))

const sites: AvailableSiteView[] = [
  {
    id: 'red_rocket',
    name: 'Red Rocket',
    flavor: 'A lonely gas station.',
    min_dweller_level: 3,
    room_total: 3,
  },
]

const choiceRoom: SiteRoomView = {
  exploration_id: 'exp-1',
  site_id: 'red_rocket',
  site_name: 'Red Rocket',
  room_index: 0,
  room_total: 3,
  room_name: 'Forecourt',
  flavor: 'The forecourt is quiet.',
  node: {
    kind: 'choice',
    prompt: 'A raider waves you over.',
    options: [
      { id: 'talk', label: 'Talk it out', stat: 'charisma', difficulty: 2, success_odds: 0.75 },
    ],
  },
  can_retreat: true,
  status: 'entered',
  outcome: null,
  finale_paid: false,
}

const clearedRoom: SiteRoomView = {
  ...choiceRoom,
  room_index: 2,
  room_name: 'Vault',
  status: 'cleared',
  finale_paid: true,
  outcome: {
    text: 'Terminal cracked: full vault! Reward vault: +40 caps.',
    damage_taken: 0,
    caps_gained: 40,
    loot_gained: ['Wonderglue (Common)'],
  },
}

const retreatedRoom: SiteRoomView = {
  ...choiceRoom,
  status: 'retreated',
  outcome: null,
}

const inRoomOutcome: SiteRoomView = {
  ...choiceRoom,
  room_index: 1,
  room_name: 'Storage',
  status: 'in_room',
  outcome: {
    text: 'Talk it out: success! Cache searched: +10 caps.',
    damage_taken: 0,
    caps_gained: 10,
    loot_gained: [],
  },
}

const mountModal = (explorationId = 'exp-1', dwellerName = 'Lucy MacLean') =>
  mount(ExpeditionSiteModal, {
    props: { show: true, explorationId, dwellerName },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

const buttonByText = (wrapper: ReturnType<typeof mountModal>, text: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(text))

describe('ExpeditionSiteModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockList.mockReset()
    mockEnter.mockReset()
    mockResolve.mockReset()
    mockRetreat.mockReset()
    mockList.mockResolvedValue(sites)
  })

  it('uses the shared wide terminal modal like other popups', () => {
    const wrapper = mountModal()

    expect(wrapper.findComponent(Dialog).props('open')).toBe(true)
  })

  it('lists available sites and enters one into the first room', async () => {
    mockEnter.mockResolvedValue(choiceRoom)
    const wrapper = mountModal()

    await flushPromises()
    expect(mockList).toHaveBeenCalledWith('exp-1')
    expect(wrapper.text()).toContain('Red Rocket')
    expect(wrapper.text()).toContain('Lv 3')
    expect(wrapper.text()).toContain('3 rooms')

    await buttonByText(wrapper, 'Enter')!.trigger('click')
    await flushPromises()

    expect(mockEnter).toHaveBeenCalledWith('exp-1', 'red_rocket')
    expect(wrapper.text()).toContain('A raider waves you over.')
    expect(wrapper.text()).toContain('Talk it out')
    expect(wrapper.text()).toContain('charisma')
    expect(wrapper.text()).toContain('75%')
  })

  it('shows the empty state when no sites are available', async () => {
    mockList.mockResolvedValue([])
    const wrapper = mountModal()

    await flushPromises()

    expect(wrapper.text()).toContain('No sites available — level up or come back later')
  })

  it('shows the load error inline', async () => {
    mockList.mockRejectedValue(new Error('boom'))
    const wrapper = mountModal()

    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load available expedition sites')
  })

  it('resolves a choice into the terminal pane and closes with updated', async () => {
    mockResolve.mockResolvedValue(clearedRoom)
    const wrapper = mountModal()
    const store = useExpeditionSiteStore()
    store.room = choiceRoom
    await flushPromises()

    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    await flushPromises()

    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'talk')
    expect(wrapper.text()).toContain('Terminal cracked: full vault! Reward vault: +40 caps.')
    expect(wrapper.text()).toContain('+40 caps')
    expect(wrapper.text()).toContain('Wonderglue (Common)')
    expect(wrapper.text()).toContain('Site cleared — rewards added to the expedition haul.')
    expect(wrapper.text()).toContain('Finale vault paid out.')

    await buttonByText(wrapper, 'Close')!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toHaveLength(1)
    expect(store.room).toBeNull()
  })

  it('shows the outcome readout above the next room actions without resolving', async () => {
    const wrapper = mountModal()
    const store = useExpeditionSiteStore()
    store.room = inRoomOutcome
    await flushPromises()

    // The just-finished result renders as an informational banner…
    expect(wrapper.text()).toContain('Cache searched: +10 caps.')
    expect(wrapper.text()).toContain('+10 caps')
    // …above the next room's node, whose actions are immediately actionable.
    expect(wrapper.text()).toContain('A raider waves you over.')
    expect(wrapper.text()).toContain('Talk it out')
    expect(wrapper.text()).toContain('75%')
    // Rendering the outcome must never trigger an API call.
    expect(mockResolve).not.toHaveBeenCalled()

    // Acting on the next room passes the explicit choice id.
    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'talk')
  })

  it('never resolves a choice node without an explicit choice id', async () => {
    const wrapper = mountModal()
    const store = useExpeditionSiteStore()
    store.room = choiceRoom
    await flushPromises()

    // A choice node offers no choice-less resolve affordance.
    expect(buttonByText(wrapper, 'Continue')).toBeUndefined()

    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    expect(mockResolve).toHaveBeenCalledTimes(1)
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'talk')
  })

  it('retreats through a confirm step and shows the retreated banner', async () => {
    mockRetreat.mockResolvedValue(retreatedRoom)
    const wrapper = mountModal()
    const store = useExpeditionSiteStore()
    store.room = choiceRoom
    await flushPromises()

    await buttonByText(wrapper, 'Retreat')!.trigger('click')
    expect(wrapper.text()).toContain('Keep Exploring')

    await buttonByText(wrapper, 'Retreat')!.trigger('click')
    await flushPromises()

    expect(mockRetreat).toHaveBeenCalledWith('exp-1')
    expect(wrapper.text()).toContain('Retreated with whatever was carried.')

    await buttonByText(wrapper, 'Close')!.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })

  it('emits close (not updated) when dismissed mid-run', async () => {
    const wrapper = mountModal()
    const store = useExpeditionSiteStore()
    store.room = choiceRoom
    await flushPromises()

    await wrapper.get('[data-slot="dialog-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toBeUndefined()
  })
})
