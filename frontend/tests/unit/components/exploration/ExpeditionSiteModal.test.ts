import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { Dialog } from '@/core/components/ui/dialog'
import { Progress } from '@/core/components/ui/progress'
import ExpeditionSiteModal from '@/modules/exploration/components/ExpeditionSiteModal.vue'
import ExpeditionRoomStepper from '@/modules/exploration/components/ExpeditionRoomStepper.vue'
import WastelandScene from '@/modules/exploration/components/WastelandScene.vue'
import SiteCombatScene from '@/modules/exploration/components/SiteCombatScene.vue'
import TriviaEncounterScene from '@/modules/exploration/components/TriviaEncounterScene.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { useExpeditionSiteStore } from '@/modules/exploration/stores/expeditionSite'
import type { AvailableSiteView, SiteRoomView } from '@/modules/exploration/api/expeditionSite'

vi.mock('@iconify/vue', () => createIconifyMock())
enableAutoUnmount(afterEach)

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
  status: 'in_room',
  outcome: null,
  finale_paid: false,
  dweller_health: 45,
  dweller_max_health: 60,
}

const triviaRoom: SiteRoomView = {
  ...choiceRoom,
  room_total: 1,
  room_name: 'Raider Tollbooth',
  flavor: 'A raider leans on a wrecked car.',
  node: {
    kind: 'trivia',
    prompt: 'The raider taps her rifle.',
    question: 'Which pre-war company built the Vaults?',
    question_id: 'q-vaults',
    raider_image_url: '/static/raider_images/variants/jinx.webp',
    raider_alt_image_url: '/static/raider_images/variants/jinx_alt.webp',
    options: [
      { id: 'vault-tec', label: 'Vault-Tec' },
      { id: 'robco', label: 'RobCo Industries' },
    ],
    enemy_names: ['Raider'],
  },
}

const outcome = (text: string, extra: Record<string, unknown> = {}) => ({
  text,
  damage_taken: 0,
  caps_gained: 0,
  loot_gained: [],
  ...extra,
})

const clearedRoom: SiteRoomView = {
  ...choiceRoom,
  room_index: 2,
  room_name: 'Vault',
  status: 'cleared',
  finale_paid: true,
  outcome: outcome('Terminal cracked: full vault! Reward vault: +40 caps.', {
    caps_gained: 40,
    loot_gained: ['Wonderglue (Common)'],
  }),
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
  outcome: outcome('Talk it out: success! Cache searched: +10 caps.', { caps_gained: 10 }),
}

const defeatedRoom: SiteRoomView = {
  ...choiceRoom,
  status: 'in_room',
  defeated: true,
  outcome: outcome('The raider pack overpowers you.', { damage_taken: 12 }),
}

const combatRoom = (overrides: Partial<SiteRoomView> = {}): SiteRoomView => {
  const room = {
    ...choiceRoom,
    room_total: 1,
    node: { kind: 'combat', prompt: 'Secure the supplies.' },
    combat_state: { round: 0, next_attack_team: 'A', fighters: [], events: [] },
    ...overrides,
  } as SiteRoomView
  useExpeditionSiteStore().room = room
  useExpeditionSiteStore().currentExplorationId = 'exp-1'
  return room
}

const mountModal = (props: Record<string, unknown> = {}, stubs: Record<string, unknown> = {}) =>
  mount(ExpeditionSiteModal, {
    props: { show: true, explorationId: 'exp-1', ...props },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' }, ...stubs } },
  })

/** The common case: a room already in the store, rendered after its data settles. */
const mountRoom = async (room: SiteRoomView, props: Record<string, unknown> = {}) => {
  useExpeditionSiteStore().room = room
  const wrapper = mountModal(props)
  await flushPromises()
  return wrapper
}

const buttonByText = (wrapper: ReturnType<typeof mountModal>, text: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(text))

beforeEach(() => {
  setActivePinia(createPinia())
  for (const mock of [mockList, mockEnter, mockResolve, mockRetreat]) mock.mockReset()
  mockList.mockResolvedValue(sites)
})

describe('ExpeditionSiteModal', () => {
  it('keeps the fight history in the shared arena log with skill labels', () => {
    const store = useExpeditionSiteStore()
    store.room = {
      ...choiceRoom,
      room_total: 1,
      node: { kind: 'combat', prompt: 'Fight' },
      combat_state: {
        round: 2,
        next_attack_team: 'A',
        fighters: [],
        events: [
          { id: '0', message: 'Encounter ready', action: null },
          { id: '1', message: 'Lucy hits Raider for 4', action: null },
          { id: '2', message: 'Raider hits Lucy for 2', action: null },
          {
            id: '3',
            message: 'Lucy uses Aimed Shot',
            action: {
              actor_id: 'lucy',
              actor_body: 'human',
              effect: 'shot',
              skill: 'Aimed Shot',
              skill_icon: 'gun-rifle',
              targets: [],
            },
          },
        ],
      },
    }
    const log = mountModal({}, { SiteCombatScene: true }).get('[aria-label="Battle log"]')

    expect(log.text()).toContain('Encounter ready')
    expect(log.text()).toContain('Lucy hits Raider for 4')
    expect(log.text()).toContain('SKILL')
    expect(log.text()).toContain('Lucy uses Aimed Shot')
  })

  it('starts arena turns only on Fight and stops advancing when the modal closes', async () => {
    vi.useFakeTimers()
    const room = combatRoom({ scene_id: 'supermarket_interior' })
    mockResolve.mockResolvedValue({ ...room, combat_state: { ...room.combat_state, round: 1 } })
    const wrapper = mountModal({}, { SiteCombatScene: true })

    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('3xl')
    expect(wrapper.findComponent(SiteCombatScene).exists()).toBe(false)
    await vi.advanceTimersByTimeAsync(2000)
    expect(mockResolve).not.toHaveBeenCalled()
    await buttonByText(wrapper, 'Fight')!.trigger('click')
    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('screen')
    expect(wrapper.findComponent(SiteCombatScene).exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(1200)
    expect(mockResolve).toHaveBeenCalledWith('exp-1', undefined, false, 0)
    expect(mockResolve).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ show: false })
    await vi.advanceTimersByTimeAsync(5000)
    expect(mockResolve).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ show: true })
    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('screen')
    await vi.advanceTimersByTimeAsync(2000)
    expect(mockResolve).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('shows a failed first automatic turn in the expanded scene and stops retrying', async () => {
    vi.useFakeTimers()
    combatRoom()
    mockResolve.mockRejectedValue(new Error('Connection lost'))
    const store = useExpeditionSiteStore()
    const wrapper = mountModal({}, { SiteCombatScene: true })

    await buttonByText(wrapper, 'Fight')!.trigger('click')
    await vi.advanceTimersByTimeAsync(1200)
    expect(store.error).toBeTruthy()
    expect(wrapper.text()).toContain(store.error!)
    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('screen')
    await vi.advanceTimersByTimeAsync(5000)
    expect(mockResolve).toHaveBeenCalledTimes(1)
    expect(buttonByText(wrapper, 'Fight')!.attributes('disabled')).toBeUndefined()
    vi.useRealTimers()
  })

  it('ends a nonlethal defeat with a return action and no retry', () => {
    useExpeditionSiteStore().room = { ...defeatedRoom, status: 'defeated', room_total: 1 }
    const wrapper = mountModal()

    expect(wrapper.text()).toContain('Escaped injured')
    expect(wrapper.text()).toContain('no site loot')
    expect(buttonByText(wrapper, 'Return to journey')).toBeTruthy()
    expect(buttonByText(wrapper, 'Push on')).toBeUndefined()
  })

  it('keeps one authored scene through the encounter and result, scoped to this explorer', async () => {
    const encounter = {
      ...choiceRoom,
      site_id: 'super_duper_mart',
      scene_id: 'supermarket_interior' as const,
      room_name: 'Supermarket Interior',
      room_index: 0,
      room_total: 1,
      node: { kind: 'combat', prompt: 'Raiders block the aisles.' },
    }
    const wrapper = await mountRoom(encounter)
    const store = useExpeditionSiteStore()
    const scene = wrapper.getComponent(WastelandScene)

    expect(scene.props('frame')).toBe('encounter')
    expect(scene.props('scene')).toBe('supermarket_interior')
    const initialSceneProps = { ...scene.props() }
    expect(wrapper.text()).not.toContain('Room 1 /')
    expect(buttonByText(wrapper, 'Fight')).toBeDefined()

    store.room = { ...encounter, status: 'cleared', outcome: clearedRoom.outcome }
    await nextTick()
    expect(wrapper.getComponent(WastelandScene).props()).toEqual(initialSceneProps)
    expect(buttonByText(wrapper, 'Return to journey')).toBeDefined()

    store.room = { ...encounter, exploration_id: 'another-expedition' }
    await nextTick()
    expect(wrapper.findComponent(WastelandScene).exists()).toBe(false)
  })

  it('uses the shared wide terminal modal like other popups', () => {
    expect(mountModal().findComponent(Dialog).props('open')).toBe(true)
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
    expect(wrapper.text()).toContain('Stat check')
    expect(wrapper.text()).toContain('CHA')
    expect(wrapper.text()).toContain('75%')
  })

  it.each([
    ['a single site', sites, 'Rachel Miller discovered a site.'],
    [
      'several sites',
      [...sites, { ...sites[0], id: 'another', name: 'Another site' }],
      'Rachel Miller discovered these sites.',
    ],
  ])('describes %s as discovered, never as a scouting choice', async (_, found, message) => {
    mockList.mockResolvedValue(found)
    const wrapper = mountModal({ dwellerName: 'Rachel Miller' })
    await flushPromises()

    expect(wrapper.text()).toContain(message)
    expect(wrapper.text()).not.toContain('Where should')
  })

  it('hides the previous explorer room before the store is reset', async () => {
    const wrapper = await mountRoom(choiceRoom)

    expect(wrapper.text()).toContain('A raider waves you over.')

    await wrapper.setProps({ explorationId: 'exp-2' })

    expect(wrapper.text()).not.toContain('A raider waves you over.')
    expect(buttonByText(wrapper, 'Talk it out')).toBeUndefined()
  })

  it.each([
    [[], null, 'No sites available on this journey.'],
    [undefined, new Error('boom'), 'Failed to load available expedition sites'],
  ])('renders the site-list fallback message (%#)', async (found, error, message) => {
    if (error) mockList.mockRejectedValue(error)
    else mockList.mockResolvedValue(found)
    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain(message)
  })

  it('resolves a choice into the terminal pane and closes with updated', async () => {
    mockResolve.mockResolvedValue(clearedRoom)
    const wrapper = await mountRoom(choiceRoom)
    const store = useExpeditionSiteStore()

    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    await flushPromises()

    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'talk')
    expect(wrapper.text()).toContain('Terminal cracked: full vault! Reward vault: +40 caps.')
    expect(wrapper.text()).toContain('+40 caps')
    expect(wrapper.text()).toContain('Wonderglue (Common)')
    expect(wrapper.text()).toContain('Site cleared — rewards added to the expedition haul.')
    expect(wrapper.text()).not.toContain('Finale vault paid out.')

    await buttonByText(wrapper, 'Close')!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toHaveLength(1)
    expect(store.room).toBeNull()
  })

  it('shows the outcome readout above the next room actions without resolving', async () => {
    const wrapper = await mountRoom(inRoomOutcome)

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
    const wrapper = await mountRoom(choiceRoom)

    // A choice node offers no choice-less resolve affordance.
    expect(buttonByText(wrapper, 'Continue')).toBeUndefined()

    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    expect(mockResolve).toHaveBeenCalledTimes(1)
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'talk')
  })

  it.each([
    ['a choice room', choiceRoom],
    ['a defeat', defeatedRoom],
  ])('retreats from %s through a confirm step and shows the retreated banner', async (_, room) => {
    mockRetreat.mockResolvedValue(retreatedRoom)
    const wrapper = await mountRoom(room)

    await buttonByText(wrapper, 'Retreat')!.trigger('click')
    expect(wrapper.text()).toContain('Keep Exploring')

    await buttonByText(wrapper, 'Retreat')!.trigger('click')
    await flushPromises()

    expect(mockRetreat).toHaveBeenCalledWith('exp-1')
    expect(wrapper.text()).toContain('Retreated with whatever was carried.')
  })

  it('renders a close-only recovery state on a non-active exploration', async () => {
    const wrapper = await mountRoom(choiceRoom, { explorationActive: false })

    expect(wrapper.text()).toContain('This expedition has ended')
    expect(buttonByText(wrapper, 'Talk it out')).toBeUndefined()
    expect(buttonByText(wrapper, 'Push on')).toBeUndefined()
    expect(buttonByText(wrapper, 'Retreat')).toBeUndefined()

    await buttonByText(wrapper, 'Close')!.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toBeUndefined()
  })

  it('emits close (not updated) when dismissed mid-run', async () => {
    const wrapper = await mountRoom(choiceRoom)

    await wrapper.get('[data-slot="dialog-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('updated')).toBeUndefined()
  })

  it('shows push-on and retreat instead of option buttons when defeated', async () => {
    const wrapper = await mountRoom(defeatedRoom)

    expect(wrapper.text()).toContain('Defeated')
    expect(wrapper.text()).toContain('The raider pack overpowers you.')
    expect(wrapper.text()).toContain('12 damage taken')
    expect(buttonByText(wrapper, 'Push on')).toBeDefined()
    expect(buttonByText(wrapper, 'Retreat')).toBeDefined()
    expect(buttonByText(wrapper, 'Talk it out')).toBeUndefined()
  })

  it('push-on retries the fight through resolveNode without a choice id', async () => {
    mockResolve.mockResolvedValue({ ...choiceRoom, room_index: 1 })
    const wrapper = await mountRoom(defeatedRoom)

    await buttonByText(wrapper, 'Push on')!.trigger('click')
    await flushPromises()

    expect(mockResolve).toHaveBeenCalledWith('exp-1', undefined)
  })

  it('renders room-pane errors and clears them on the next action', async () => {
    const wrapper = await mountRoom(choiceRoom)
    const store = useExpeditionSiteStore()
    store.error = 'Failed to resolve expedition node'
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to resolve expedition node')

    mockResolve.mockResolvedValue({ ...choiceRoom, room_index: 1 })
    await buttonByText(wrapper, 'Talk it out')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Failed to resolve expedition node')
  })

  it.each([
    ['an encounter is open', {}],
    ['travel is paused for an open report', { pausesTravel: true }],
  ])('shows travel paused when %s', async (_, props) => {
    const wrapper = await mountRoom(choiceRoom, props)

    expect(wrapper.text()).toContain('Travel paused')
    expect(wrapper.text()).not.toContain('Travel continues')
    expect(wrapper.text()).not.toContain('Clock expiry')
  })

  it('renders stat-check options with a compact SPECIAL chip and inspectable detail', async () => {
    const wrapper = await mountRoom({
      ...choiceRoom,
      node: {
        ...choiceRoom.node,
        options: [
          {
            id: 'disarm',
            label: 'Disarm the wires (Perception)',
            stat: 'perception',
            difficulty: 1,
            success_odds: 0.95,
          },
        ],
      },
    })

    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('5xl')
    expect(wrapper.text()).toContain('Stat check')
    expect(wrapper.text()).toContain('Disarm the wires')
    expect(wrapper.text()).not.toContain('(Perception)')
    expect(wrapper.text()).toContain('PER')
    expect(wrapper.text()).toContain('95%')

    const option = buttonByText(wrapper, 'Disarm the wires')!
    expect(option.attributes('title')).toBe('Perception check · Difficulty 1 · 95% success')
    expect(option.attributes('aria-label')).toContain('Perception check')
  })

  it('uses the full-width room card and stepper for multi-room stat checks', async () => {
    const wrapper = await mountRoom({
      ...choiceRoom,
      room_index: 1,
      room_total: 3,
      room_name: 'Collapsed Aisles',
      room_names: ['Parking Lot', 'Collapsed Aisles', 'Storage Room'],
      node: {
        kind: 'choice',
        prompt: 'How do you take the aisles?',
        options: [
          {
            id: 'sneak',
            label: 'Sneak through (Agility)',
            stat: 'agility',
            difficulty: 2,
            success_odds: 0.75,
          },
          {
            id: 'sweep',
            label: 'Loud sweep (Strength)',
            stat: 'strength',
            difficulty: 1,
            success_odds: 0.85,
          },
          {
            id: 'call',
            label: 'Call out (Charisma)',
            stat: 'charisma',
            difficulty: 3,
            success_odds: 0.65,
          },
        ],
      },
    })

    expect(wrapper.findComponent(ExpeditionRoomStepper).exists()).toBe(true)
    expect(wrapper.text()).toContain('Parking Lot')
    expect(wrapper.text()).toContain('Collapsed Aisles')
    expect(wrapper.text()).toContain('Storage Room')
    expect(wrapper.text()).toContain('AGI')
    expect(wrapper.text()).toContain('STR')
    expect(wrapper.text()).toContain('CHA')
    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('5xl')
  })

  it('explains an expired report without fetching offers for a finished journey', async () => {
    const wrapper = mountModal({ explorationActive: false })
    await wrapper.setProps({ reportedSiteId: 'red_rocket' })
    await flushPromises()

    expect(mockList).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('This journey has finished')
    expect(wrapper.text()).toContain('This site report is no longer available')
    expect(buttonByText(wrapper, 'Enter')).toBeUndefined()
  })

  it('opens a reported site for review without automatically entering', async () => {
    const wrapper = mountModal()
    await wrapper.setProps({ reportedSiteId: 'red_rocket' })
    await flushPromises()

    expect(wrapper.text()).toContain('including during the return trip')
    expect(wrapper.find('.ring-2').exists()).toBe(true)
    expect(mockEnter).not.toHaveBeenCalled()

    await wrapper.setProps({ reportedSiteId: 'spent-site' })
    expect(wrapper.text()).toContain('This site report is no longer available')
  })

  it('renders a trivia question with plain answer buttons', async () => {
    const wrapper = await mountRoom(triviaRoom)

    expect(wrapper.getComponent(TerminalModal).props('size')).toBe('screen')
    expect(wrapper.text()).toContain('Which pre-war company built the Vaults?')
    expect(wrapper.text()).toContain('If it goes wrong: Raider')
    const portrait = wrapper.get('img[alt="Raider posing the question"]')
    expect(portrait.attributes('src')).toContain('/static/raider_images/variants/jinx')
    const answers = wrapper
      .findAll('button')
      .filter((button) =>
        ['Vault-Tec', 'RobCo Industries'].some((label) => button.text().includes(label))
      )
    expect(answers).toHaveLength(2)
    for (const answer of answers) expect(answer.text()).not.toContain('%')
  })

  it('sends the current question id with a trivia answer', async () => {
    const wrapper = await mountRoom(triviaRoom)
    mockResolve.mockResolvedValue(triviaRoom)

    await buttonByText(wrapper, 'Vault-Tec')!.trigger('click')
    await flushPromises()

    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'vault-tec', false, undefined, 'q-vaults')
  })

  const wrongAnswerRoom = (): SiteRoomView => ({
    ...triviaRoom,
    node: { ...triviaRoom.node, options: [] },
    outcome: {
      text: 'Wrong answer — the raider attacks!',
      damage_taken: 0,
      caps_gained: 0,
      loot_gained: [],
    },
    combat_state: { round: 0, next_attack_team: 'A', fighters: [], events: [] },
  })

  it('treats a started trivia fight as combat and shows the wrong-answer outcome', async () => {
    const wrapper = await mountRoom(wrongAnswerRoom())

    expect(wrapper.text()).toContain('Wrong answer — the raider attacks!')
    expect(buttonByText(wrapper, 'Fight')).toBeTruthy()
  })

  it('starts the trivia fight immediately when a wrong answer opens it', async () => {
    vi.useFakeTimers()
    const room = wrongAnswerRoom()
    useExpeditionSiteStore().room = room
    useExpeditionSiteStore().currentExplorationId = 'exp-1'
    mockResolve.mockResolvedValue({ ...room, combat_state: { ...room.combat_state, round: 1 } })
    const wrapper = mountModal({}, { SiteCombatScene: true })

    await nextTick()
    expect(wrapper.findComponent(SiteCombatScene).exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(1200)
    expect(mockResolve).toHaveBeenCalledWith('exp-1', undefined, false, 0)
    vi.useRealTimers()
  })

  it('dedupes combat enemies and labels failure threats separately', async () => {
    const wrapper = await mountRoom({
      ...choiceRoom,
      node: {
        kind: 'combat',
        prompt: 'Ambush between the cars!',
        options: [],
        enemy_names: ['Radroach swarm', 'Radroach swarm', 'Raider gang'],
      },
    })

    expect(
      wrapper.get('[aria-label="Encounter status"] [aria-label="Encounter enemies"]').text()
    ).toContain('Radroach swarm ×2, Raider gang')

    useExpeditionSiteStore().room = {
      ...choiceRoom,
      node: {
        kind: 'choice',
        prompt: 'A raider waves you over.',
        options: [],
        enemy_names: ['Giant Radscorpion'],
      },
    }
    await flushPromises()

    expect(wrapper.text()).toContain('If it goes wrong: Giant Radscorpion')
  })

  it.each([
    ['danger', 15, 60, 25],
    ['warning', 30, 60, 50],
    ['default', 48, 60, 80],
  ])(
    'renders the dweller HP bar with the %s tone from health fields',
    async (tone, health, max, value) => {
      const wrapper = await mountRoom({
        ...choiceRoom,
        dweller_health: health,
        dweller_max_health: max,
      })

      expect(wrapper.text()).toContain(`HP ${health}/${max}`)
      expect(wrapper.findComponent(Progress).exists()).toBe(true)
      expect(wrapper.findComponent(Progress).props('modelValue')).toBe(value)
      expect(wrapper.findComponent(Progress).props('tone')).toBe(tone)
    }
  )

  it('hides the HP bar when max health is unknown', async () => {
    const wrapper = await mountRoom({ ...choiceRoom, dweller_health: 0, dweller_max_health: 0 })

    expect(wrapper.text()).not.toContain('HP ')
    expect(wrapper.findComponent(Progress).exists()).toBe(false)
  })

  it('renders per-enemy combat results after a resolve', async () => {
    const wrapper = await mountRoom({
      ...choiceRoom,
      node: {
        kind: 'combat',
        prompt: 'Ambush between the cars!',
        options: [],
        enemy_names: ['Radroach swarm', 'Raider gang'],
      },
      outcome: {
        text: 'The pack scatters.',
        damage_taken: 8,
        caps_gained: 0,
        loot_gained: [],
        combat: [
          { enemy: 'Radroach swarm', victory: true, damage_taken: 2 },
          { enemy: 'Raider gang', victory: false, damage_taken: 6 },
        ],
      },
    })

    expect(wrapper.text()).toContain('Radroach swarm')
    expect(wrapper.text()).toContain('defeated')
    expect(wrapper.text()).toContain('Raider gang')
    expect(wrapper.text()).toContain('overpowered')
    expect(wrapper.text()).toContain('-2')
    expect(wrapper.text()).toContain('-6')
    // The pre-fight deduped preview is replaced by the per-enemy results.
    expect(wrapper.text()).not.toContain('Enemies: Radroach swarm')
  })

  it('keeps a won fight visible after advancing to a non-combat room', async () => {
    const wrapper = await mountRoom({
      ...choiceRoom,
      room_name: 'Prize Stock',
      node: { kind: 'finale', prompt: 'Open the vault.', options: [], enemy_names: [] },
      outcome: {
        text: 'Defeated the pack!',
        damage_taken: 3,
        caps_gained: 0,
        loot_gained: [],
        combat: [
          { enemy: 'Mole Rat pack', victory: true, damage_taken: 1 },
          { enemy: 'Mole Rat pack', victory: true, damage_taken: 2 },
        ],
      },
    })

    expect(wrapper.findAll('[aria-label="Fight results"] li')).toHaveLength(2)
    expect(wrapper.text()).toContain('Mole Rat pack')
    expect(wrapper.text()).not.toContain('If it goes wrong:')
    expect(wrapper.text()).toContain('Open the vault.')
  })

  it('flashes the damage taken on the HP bar after a damaging resolve', async () => {
    vi.useFakeTimers()
    const wrapper = await mountRoom({ ...choiceRoom, dweller_health: 45, dweller_max_health: 60 })

    expect(wrapper.text()).not.toContain('-8')

    useExpeditionSiteStore().room = {
      ...choiceRoom,
      dweller_health: 37,
      dweller_max_health: 60,
      outcome: { text: 'Ouch.', damage_taken: 8, caps_gained: 0, loot_gained: [] },
    }
    await nextTick()

    expect(wrapper.text()).toContain('-8')

    vi.advanceTimersByTime(1700)
    await nextTick()

    expect(wrapper.text()).not.toContain('-8')
    vi.useRealTimers()
  })

  it('explains the retreat keeps the encounter open for the journey', async () => {
    const wrapper = await mountRoom(choiceRoom)

    await buttonByText(wrapper, 'Retreat')!.trigger('click')

    expect(wrapper.text()).toContain('keeps this encounter open')
    expect(wrapper.text()).toContain('Keep Exploring')
  })

  it.each([
    ['trivia', triviaRoom, null],
    ['terminal', retreatedRoom, 'Retreated with whatever was carried.'],
  ])('keeps a %s recovery run close-only', async (_, room, banner) => {
    const wrapper = await mountRoom(room, { explorationActive: false })

    expect(wrapper.text()).toContain('This expedition has ended')
    if (banner) {
      expect(wrapper.text()).toContain(banner)
    } else {
      expect(wrapper.findComponent(TriviaEncounterScene).exists()).toBe(false)
      expect(buttonByText(wrapper, 'Vault-Tec')).toBeUndefined()
    }
    expect(buttonByText(wrapper, 'Close')).toBeDefined()
  })
})
