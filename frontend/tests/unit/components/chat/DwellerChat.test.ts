import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { createAxiosMock, createIconifyMock, createToastMock } from '../../helpers/mocks'
import { ref } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerChat from '@/modules/chat/components/DwellerChat.vue'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useDwellerDeathStore } from '@/modules/dwellers/stores/dwellerDeath'
import { useProfileStore } from '@/modules/profile/stores/profile'
import * as trainingService from '@/modules/progression/services/trainingService'

// iconify's Icon ships with no component name, so VTU stubs can't match it — mock the module instead.
vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-stub" :data-icon="icon"></span>' })
)
vi.mock('@/core/plugins/axios', () => createAxiosMock())
vi.mock('@/modules/chat/composables/useAudioRecorder', () => ({
  useAudioRecorder: () => ({
    recordingState: { value: 'inactive' },
    recordingDuration: { value: 0 },
    isRecording: { value: false },
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
    cancelRecording: vi.fn(),
    formatDuration: vi.fn(
      (d: number) => `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`
    ),
  }),
}))

// Mock useChatWebSocket and capture the handlers the component subscribes to.
const mockWebSocketHandlers: Record<string, Function[]> = {}
const mockWsState = { value: 'disconnected' as 'connected' | 'disconnected' }
const mockSendMessage = vi.fn()
vi.mock('@/core/composables/useWebSocket', () => ({
  useChatWebSocket: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendTypingIndicator: vi.fn(),
    sendMessage: mockSendMessage,
    on: (event: string, handler: Function) => {
      mockWebSocketHandlers[event] = [...(mockWebSocketHandlers[event] ?? []), handler]
    },
    state: mockWsState,
  }),
}))

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/modules/progression/services/trainingService', () => ({ startTraining: vi.fn() }))
vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({
    activeVault: {},
    activeVaultId: 'vault-123',
    loadedVaults: { 'vault-123': { id: 'vault-123', stimpack: 10, radaway: 10 } },
  }),
}))

const trainingRoom = (id: string, ability: string | null, extra: object = {}) => ({
  id,
  name: id,
  category: 'training',
  ability,
  max_capacity: 5,
  ...extra,
})
const DEFAULT_ROOMS = [
  trainingRoom('training-room-789', 'STRENGTH'),
  { id: 'room-456', name: 'Power Plant', category: 'production', ability: null, max_capacity: 3 },
]
const mockRooms = ref<any[]>(DEFAULT_ROOMS)
const { mockFetchRooms } = vi.hoisted(() => ({ mockFetchRooms: vi.fn() }))
vi.mock('@/modules/rooms/stores/room', () => ({
  useRoomStore: () => ({
    get rooms() {
      return mockRooms.value
    },
    fetchRooms: mockFetchRooms,
  }),
}))

const {
  mockSendDwellerToWasteland,
  mockRecallDweller,
  mockCompleteExploration,
  mockFetchExplorationProgress,
} = vi.hoisted(() => ({
  mockSendDwellerToWasteland: vi.fn(),
  mockRecallDweller: vi.fn(),
  mockCompleteExploration: vi.fn(),
  mockFetchExplorationProgress: vi.fn(),
}))
vi.mock('@/modules/exploration/stores/exploration', () => ({
  useExplorationStore: () => ({
    sendDwellerToWasteland: mockSendDwellerToWasteland,
    recallDweller: mockRecallDweller,
    completeExploration: mockCompleteExploration,
    fetchExplorationProgress: mockFetchExplorationProgress,
  }),
}))

const { mockSuggestHeading } = vi.hoisted(() => ({ mockSuggestHeading: vi.fn() }))
vi.mock('@/modules/exploration/api/exploration', () => ({
  explorationApi: { suggestHeading: mockSuggestHeading, dispatchToLocation: vi.fn() },
}))

const { mockRefreshMap } = vi.hoisted(() => ({ mockRefreshMap: vi.fn() }))
const mockMapLocations = ref<any[]>([])
vi.mock('@/modules/map/stores/map', () => ({
  useMapStore: () => ({
    locations: mockMapLocations.value,
    unlockedPlacesCount: ref(0),
    fetchMap: mockRefreshMap,
    refreshMap: mockRefreshMap,
  }),
}))

const defaultProps = {
  dwellerId: 'dweller-123',
  dwellerName: 'Test Dweller',
  username: 'TestUser',
  dwellerAvatar: undefined,
  vaultId: 'vault-123',
}

const mountChat = (props: Record<string, unknown> = {}) =>
  mount(DwellerChat, {
    props: { ...defaultProps, ...props },
    global: {
      stubs: {
        Icon: { template: '<span class="icon-stub" :data-icon="icon"></span>', props: ['icon'] },
        // The chat's send-wasteland modal teleports; render it inline so tests can interact.
        Teleport: { template: '<div><slot /></div>' },
      },
    },
  })

const mounted = async (props: Record<string, unknown> = {}) => {
  const wrapper = mountChat(props)
  await flushPromises()
  return wrapper
}

/** Send `text` through the composer, queueing one reply payload for the POST. */
const send = async (
  wrapper: VueWrapper,
  text: string,
  reply: Record<string, unknown> = {}
): Promise<void> => {
  ;(apiClient.post as Mock).mockResolvedValueOnce({
    data: { response: 'ok', happiness_impact: null, action_suggestion: null, ...reply },
  })
  await wrapper.get('.chat-input-field').setValue(text)
  await wrapper.get('.chat-send-btn').trigger('click')
  await flushPromises()
}

const confirmAction = async (wrapper: VueWrapper) => {
  await wrapper.get('.action-confirm-btn').trigger('click')
  await flushPromises()
}

const openSendModal = async (wrapper: VueWrapper) => {
  await confirmAction(wrapper)
  await wrapper.get('.modal-button.confirm').trigger('click')
  await flushPromises()
}

/** A dweller row shaped like the store's filter list, with the fields the chat reads. */
const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'dweller-123',
  first_name: 'Test',
  last_name: 'Dweller',
  room_id: null,
  level: 1,
  happiness: 50,
  strength: 5,
  perception: 5,
  endurance: 5,
  charisma: 5,
  intelligence: 5,
  agility: 5,
  luck: 5,
  status: 'idle',
  age_group: 'adult',
  ...overrides,
})

const seedDwellers = (...rows: object[]) =>
  useDwellerStore().filter.$patch({ dwellers: rows.length ? rows : [dweller()] })

const explorationReply = (overrides: Record<string, unknown> = {}) => ({
  response: 'Ready to explore!',
  action_suggestion: {
    action_type: 'start_exploration',
    duration_hours: 8,
    stimpaks: 5,
    radaways: 3,
    reason: 'Good stats for exploration',
  },
  ...overrides,
})

/** A reply payload; tests only read the fields they pass. */
const wsReply = (
  id: string,
  response = 'Noted.',
  suggestion: Record<string, unknown> | null = null
) => ({
  dweller_message_id: id,
  response,
  happiness_impact: null,
  action_suggestion: suggestion,
})

/** Spy on the dweller management action behind the chat's confirm handlers. */
const stubManagement = (method: 'assignDwellerToRoom' | 'unassignDwellerFromRoom') =>
  vi.spyOn(useDwellerStore().management, method).mockResolvedValue({} as never)

describe('DwellerChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    mockWsState.value = 'disconnected'
    for (const event of Object.keys(mockWebSocketHandlers)) mockWebSocketHandlers[event] = []

    mockSendDwellerToWasteland.mockReset()
    mockRecallDweller.mockReset()
    mockCompleteExploration.mockReset()
    mockFetchExplorationProgress.mockReset()
    mockFetchRooms.mockReset()
    mockSuggestHeading.mockReset()
    mockSuggestHeading.mockResolvedValue(null)
    mockRooms.value = DEFAULT_ROOMS
    mockMapLocations.value = []

    useAuthStore().$patch({
      token: 'test-token',
      user: { id: 'user-123', username: 'TestUser' },
    })
    ;(apiClient.get as Mock).mockResolvedValue({ data: [] })
  })

  describe('Conversation starters', () => {
    it('prefills the composer from a known place without sending a message', async () => {
      mockMapLocations.value = [
        { id: 'megaton', name: 'Megaton', dwellers: [{ dweller_id: 'dweller-123' }] },
      ]
      const wrapper = await mounted()

      await wrapper.get('.conversation-starter').trigger('click')

      expect((wrapper.get('.chat-input-field').element as HTMLInputElement).value).toBe(
        'What can you tell me about Megaton?'
      )
      expect(apiClient.post).not.toHaveBeenCalled()
    })
  })

  describe('Dweller activity', () => {
    it('shows the dweller assignment in the chat header', async () => {
      const wrapper = mountChat({ dwellerStatus: 'working', roomName: 'Power Plant' })

      expect(wrapper.get('.identity-status').text()).toBe('ON DUTY · POWER PLANT')
    })
  })

  describe('Voice verification reminder', () => {
    const reminder = '.voice-verification-reminder'

    const signIn = (emailVerified: boolean) =>
      useAuthStore().$patch({
        user: { id: 'user-123', username: 'TestUser', email_verified: emailVerified },
      })

    it.each([
      ['text mode', false, false, false],
      ['voice, unverified', false, true, true],
      ['voice, verified', true, true, false],
    ])(
      'shows the reminder only for unverified voice users (%s)',
      async (_case, verified, voice, shown) => {
        signIn(verified as boolean)
        const wrapper = await mounted()
        if (voice) await wrapper.get('button[aria-label="Switch to voice input"]').trigger('click')

        expect(wrapper.find(reminder).exists()).toBe(shown)
        if (shown) expect(wrapper.get(reminder).text()).toContain('Voice chat uses AI credits')
      }
    )

    it('resends the verification email from the reminder', async () => {
      signIn(false)
      const resendSpy = vi.spyOn(useAuthStore(), 'resendVerificationEmail').mockResolvedValue(true)
      const wrapper = await mounted()

      await wrapper.get('button[aria-label="Switch to voice input"]').trigger('click')
      await wrapper.get(reminder).get('button').trigger('click')
      await flushPromises()

      expect(resendSpy).toHaveBeenCalledOnce()
      expect(wrapper.get(reminder).text()).toContain('EMAIL SENT')
    })
  })

  describe('Happiness impact', () => {
    it.each([
      [5, '+5', 'mdi:emoticon-happy'],
      [-3, '-3', 'mdi:emoticon-sad'],
      [0, '0', 'mdi:emoticon-neutral'],
    ])('renders a %s delta badge', async (delta, label, icon) => {
      const wrapper = await mounted()
      await send(wrapper, 'Hello there!', {
        response: 'Noted.',
        happiness_impact: { delta, reason_text: 'Conversation' },
      })

      const badge = wrapper.get('.happiness-indicator')
      expect(badge.text()).toContain(label)
      expect(badge.get('.icon-stub').attributes('data-icon')).toBe(icon)
    })

    it('omits the badge when the reply carries no happiness impact', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Hi', { response: 'Hello!' })

      expect(wrapper.find('.happiness-indicator').exists()).toBe(false)
    })
  })

  describe('Action suggestions', () => {
    const assignSuggestion = {
      action_type: 'assign_to_room',
      room_id: 'room-456',
      room_name: 'Power Plant',
      reason: 'High strength makes this a great fit',
    }

    it.each([
      {
        suggestion: assignSuggestion,
        reply: {
          response: 'I would love to work in the power plant!',
          happiness_impact: { delta: 2, reason_text: 'Excited about work' },
        },
        label: 'Assign to Power Plant',
      },
      {
        suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength, needs improvement',
        },
        reply: {
          response: 'I want to get stronger!',
          happiness_impact: { delta: 3, reason_text: 'Motivated' },
        },
        label: 'Train strength',
      },
    ])(
      'renders a $suggestion.action_type card with its reason and confirm button',
      async (testCase) => {
        const wrapper = await mounted()
        await send(wrapper, 'What next?', {
          ...testCase.reply,
          action_suggestion: testCase.suggestion,
        })

        const card = wrapper.get('.action-suggestion-card')
        expect(card.text()).toContain('Suggested Action')
        expect(card.text()).toContain(testCase.label)
        expect(card.text()).toContain(testCase.suggestion.reason)
        expect(wrapper.get('.action-confirm-btn').text()).toContain('Confirm')
      }
    )

    it('assigns the dweller and clears the card on confirm', async () => {
      const assignSpy = stubManagement('assignDwellerToRoom')
      const wrapper = await mounted()
      await send(wrapper, 'Work assignment', {
        response: 'I would love to work there!',
        action_suggestion: assignSuggestion,
      })

      await confirmAction(wrapper)

      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'room-456')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('spends a carried stimpak when the medical request is confirmed', async () => {
      useDwellerStore().filter.$patch({
        detailedDwellers: {
          'dweller-123': { id: 'dweller-123', stimpack: 1, radaway: 0 } as any,
        },
      })
      const useStimpackSpy = vi
        .spyOn(useDwellerStore().medical, 'useStimpack')
        .mockResolvedValue({} as any)
      const wrapper = await mounted()
      await send(wrapper, 'I feel very weak.', {
        response: 'Please, Overseer. I need a Stimpak.',
        action_suggestion: { action_type: 'request_stimpak', reason: 'Health is below 50%.' },
      })

      expect(wrapper.get('.action-suggestion-card').text()).toContain('Give Stimpak')
      await confirmAction(wrapper)

      expect(useStimpackSpy).toHaveBeenCalledWith('dweller-123')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('starts training in the dweller room on confirm', async () => {
      seedDwellers(dweller({ room_id: 'training-room-789' }))
      const wrapper = await mounted()
      await send(wrapper, 'Train me', {
        response: 'Ready to train!',
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Needs strength training',
        },
      })

      await confirmAction(wrapper)

      expect(trainingService.startTraining).toHaveBeenCalledWith('dweller-123', 'training-room-789')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('dismisses the card without acting', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Suggest something', {
        response: 'Work suggestion',
        action_suggestion: { ...assignSuggestion, room_id: 'room-123', room_name: 'Diner' },
      })

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
      await wrapper.get('.action-dismiss-btn').trigger('click')
      await flushPromises()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it.each([
      ['an explicit no_action', { action_type: 'no_action', reason: 'No action needed' }],
      ['no suggestion at all', null],
    ])('renders no card for %s', async (_case, suggestion) => {
      const wrapper = await mounted()
      await send(wrapper, 'Just saying hi', {
        response: 'Just chatting.',
        action_suggestion: suggestion,
      })

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })
  })

  describe('Message sending', () => {
    it('sends the message, renders the reply and disables an empty composer', async () => {
      const wrapper = await mounted()
      expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(true)

      await send(wrapper, 'Hello!', { response: 'Hello, Overseer!' })

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/chat/dweller-123',
        { message: 'Hello!' },
        { params: { debug: undefined } }
      )
      expect(wrapper.findAll('.message-wrapper')).toHaveLength(2)
      expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(true)
    })

    it('enables the send button once the composer has text', async () => {
      const wrapper = mountChat()

      await wrapper.get('.chat-input-field').setValue('Hello')

      expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(false)
    })

    it('shows the typing indicator while a reply is outstanding', async () => {
      const wrapper = await mounted()
      ;(apiClient.post as Mock).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: { response: 'Hi' } }), 100))
      )

      await wrapper.get('.chat-input-field').setValue('Hello')
      await wrapper.get('.chat-send-btn').trigger('click')

      expect(wrapper.find('.typing-indicator').exists()).toBe(true)
    })
  })

  describe('Rendering', () => {
    it('renders the chat container with the dweller name', () => {
      const wrapper = mountChat()

      expect(wrapper.get('.identity-name').text()).toBe('Test Dweller')
      expect(wrapper.find('.chat-container').exists()).toBe(true)
    })
  })

  describe('WebSocket typing indicator', () => {
    it('tolerates typing before the socket connects', async () => {
      const wrapper = await mounted()
      const input = wrapper.get('.chat-input-field')

      expect(() => input.trigger('input')).not.toThrow()
      await input.setValue('H')
      await input.trigger('input')

      expect(wrapper.find('.chat-input-field').exists()).toBe(true)
    })
  })

  describe('WebSocket happiness and action updates', () => {
    const reply = (id: string, response: string) => wsReply(id, response)

    it('updates only the dweller message addressed by message_id', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'First message', reply('msg-first', 'First response'))
      await send(wrapper, 'Second message', reply('msg-second', 'Second response'))
      expect(wrapper.findAll('.message-wrapper')).toHaveLength(4)

      mockWebSocketHandlers['happiness_update'][0]({
        message_id: 'msg-second',
        happiness_impact: { delta: 5, reason_text: 'Good conversation' },
      })
      await wrapper.vm.$nextTick()

      const dwellerMessages = wrapper.findAll('.message-wrapper.dweller')
      expect(dwellerMessages).toHaveLength(2)
      expect(dwellerMessages[0].find('.happiness-indicator').exists()).toBe(false)
      expect(dwellerMessages[1].get('.happiness-indicator').text()).toContain('+5')
    })

    it('ignores a happiness update without a message_id', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Test', reply('msg-1', 'A response'))

      mockWebSocketHandlers['happiness_update'][0]({
        happiness_impact: { delta: 3, reason_text: 'No message_id' },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.happiness-indicator').exists()).toBe(false)
    })

    it('attaches an action suggestion only to the latest message', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'First message', reply('msg-first', 'First response'))
      await send(wrapper, 'Second message', reply('msg-second', 'Second response'))

      mockWebSocketHandlers['action_suggestion'][0]({
        message_id: 'msg-second',
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-123',
          room_name: 'Power Plant',
          reason: 'Good fit',
        },
      })
      await wrapper.vm.$nextTick()

      const cards = wrapper.findAll('.action-suggestion-card')
      expect(cards).toHaveLength(1)
      const messages = wrapper.findAll('.message-wrapper')
      expect(messages.at(-1)!.find('.action-suggestion-card').exists()).toBe(true)
      expect(messages.at(-1)!.text()).toContain('Assign to Power Plant')
    })
  })

  describe('Training room selection', () => {
    const trainReply = {
      response: 'I want to get stronger!',
      happiness_impact: { delta: 3, reason_text: 'Motivated' },
      action_suggestion: {
        action_type: 'start_training',
        stat: 'strength',
        reason: 'Low strength, needs improvement',
      },
    }

    it.each([
      {
        name: 'the only available training room',
        rooms: DEFAULT_ROOMS,
        dwellerRoom: 'room-456',
        expected: 'training-room-789',
      },
      {
        name: 'the stat-matching room over a generic one',
        rooms: [
          trainingRoom('generic-training', 'ENDURANCE'),
          trainingRoom('strength-training', 'STRENGTH'),
          { id: 'room-456', name: 'Power Plant', category: 'production', ability: null },
        ],
        dwellerRoom: 'room-456',
        expected: 'strength-training',
      },
      {
        name: 'any training room when no stat matches',
        rooms: [trainingRoom('endurance-training', 'ENDURANCE')],
        dwellerRoom: null,
        expected: 'endurance-training',
      },
      {
        name: 'a fallback when the matching room is full',
        rooms: [
          trainingRoom('strength-training', 'STRENGTH', { size: 3 }),
          trainingRoom('endurance-training', 'ENDURANCE', { size_min: 6 }),
        ],
        dwellerRoom: null,
        fillers: [{ room: 'strength-training', count: 2 }],
        expected: 'endurance-training',
      },
      {
        name: 'an error when no training rooms exist',
        rooms: [{ id: 'room-456', name: 'Power Plant', category: 'production', ability: null }],
        dwellerRoom: 'room-456',
        error: 'No training rooms available',
      },
      {
        name: 'an error when every training room is at capacity',
        rooms: [
          trainingRoom('strength-training', 'STRENGTH', { max_capacity: 5 }),
          trainingRoom('endurance-training', 'ENDURANCE', { max_capacity: 3 }),
        ],
        dwellerRoom: 'room-456',
        fillers: [
          { room: 'strength-training', count: 5 },
          { room: 'endurance-training', count: 3 },
        ],
        error: 'No available training rooms (all at capacity)',
      },
    ])('picks $name', async ({ rooms, dwellerRoom, fillers, expected, error }) => {
      mockRooms.value = rooms
      const fillers_ = (fillers ?? []).flatMap(({ room, count }) =>
        Array.from({ length: count }, (_, i) =>
          dweller({ id: `${room}-filler-${i}`, room_id: room, first_name: 'Filler' })
        )
      )
      seedDwellers(...fillers_, dweller({ room_id: dwellerRoom }))
      const assignSpy = stubManagement('assignDwellerToRoom')
      const wrapper = await mounted()
      await send(wrapper, 'Train me', trainReply)

      await confirmAction(wrapper)

      if (error) {
        expect(mockToast.error).toHaveBeenCalledWith(error)
        expect(assignSpy).not.toHaveBeenCalled()
        return
      }
      expect(assignSpy).toHaveBeenCalledWith('dweller-123', expected)
      expect(trainingService.startTraining).toHaveBeenCalledWith('dweller-123', expected)
    })

    it('fetches rooms from the room store when the vault carries none', async () => {
      mockRooms.value = []
      mockFetchRooms.mockImplementation(() => {
        mockRooms.value = [trainingRoom('training-room-789', 'STRENGTH')]
        return Promise.resolve()
      })
      seedDwellers(dweller({ room_id: 'room-456' }))
      const assignSpy = stubManagement('assignDwellerToRoom')
      const wrapper = await mounted()
      await send(wrapper, 'Train', trainReply)

      await confirmAction(wrapper)

      expect(mockFetchRooms).toHaveBeenCalledWith('vault-123')
      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'training-room-789')
      expect(trainingService.startTraining).toHaveBeenCalledWith('dweller-123', 'training-room-789')
    })
  })

  describe('Sticky latest suggestion', () => {
    const reply = (id: string, suggestion: object | null) => wsReply(id, 'Noted.', suggestion)

    it('shows only the latest card when several messages carry suggestions', async () => {
      const wrapper = await mounted()
      await send(
        wrapper,
        'Where do you want to work?',
        reply('msg-1', {
          action_type: 'assign_to_room',
          room_id: 'room-111',
          room_name: 'Diner',
          reason: 'Good fit for diner',
        })
      )
      await send(
        wrapper,
        'Changed your mind?',
        reply('msg-2', {
          action_type: 'assign_to_room',
          room_id: 'room-222',
          room_name: 'Power Plant',
          reason: 'High strength',
        })
      )

      const cards = wrapper.findAll('.action-suggestion-card')
      expect(cards).toHaveLength(1)
      expect(cards[0].text()).toContain('Power Plant')
      expect(cards[0].text()).not.toContain('Diner')
    })

    it.each([
      ['a null suggestion', null],
      ['an explicit no_action', { action_type: 'no_action', reason: 'Just conversing' }],
    ])('keeps the previous actionable card for %s', async (_case, suggestion) => {
      const wrapper = await mounted()
      await send(
        wrapper,
        'What should you do?',
        reply('msg-1', { action_type: 'start_training', stat: 'strength', reason: 'Low strength' })
      )
      expect(wrapper.get('.action-suggestion-card').text()).toContain('Train strength')

      await send(wrapper, 'How are you feeling?', reply('msg-2', suggestion))

      const card = wrapper.get('.action-suggestion-card')
      expect(card.text()).toContain('Train strength')
    })
  })

  describe('WebSocket message id correlation', () => {
    const reply = (id: string, response: string) => wsReply(id, response)

    it.each([
      {
        name: 'two replies, event for the older one',
        replies: [
          ['First question', 'msg-A'],
          ['Second question', 'msg-B'],
        ],
        suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-target',
          room_name: 'Target Room',
          reason: 'Targeted update',
        },
        label: 'Target Room',
      },
      {
        name: 'three replies, late event for the first',
        replies: [
          ['Message A', 'msg-A'],
          ['Message B', 'msg-B'],
          ['Message C', 'msg-C'],
        ],
        suggestion: {
          action_type: 'start_training',
          stat: 'perception',
          reason: 'Delayed suggestion',
        },
        label: 'Train perception',
      },
    ])(
      'targets the matching message even when it is not the latest ($name)',
      async ({ replies, suggestion, label }) => {
        const wrapper = await mounted()
        for (const [text, id] of replies) await send(wrapper, text, reply(id, `Reply ${id}`))
        expect(wrapper.findAll('.message-wrapper')).toHaveLength(replies.length * 2)
        expect(wrapper.findAll('.action-suggestion-card')).toHaveLength(0)

        mockWebSocketHandlers['action_suggestion'][0]({
          type: 'action_suggestion',
          message_id: 'msg-A',
          action_suggestion: suggestion,
        })
        await wrapper.vm.$nextTick()

        expect(wrapper.findAll('.action-suggestion-card')).toHaveLength(1)
        const dwellerMessages = wrapper.findAll('.message-wrapper.dweller')
        expect(dwellerMessages).toHaveLength(replies.length)
        expect(dwellerMessages[0].get('.action-suggestion-card').exists()).toBe(true)
        expect(dwellerMessages[0].text()).toContain(label)
        for (const later of dwellerMessages.slice(1)) {
          expect(later.find('.action-suggestion-card').exists()).toBe(false)
        }
      }
    )

    it('ignores an event for an unknown message_id', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Test message', reply('msg-real', 'Real response'))

      mockWebSocketHandlers['action_suggestion'][0]({
        type: 'action_suggestion',
        message_id: 'msg-nonexistent',
        action_suggestion: { action_type: 'assign_to_room', room_id: 'room-123', room_name: 'X' },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.action-suggestion-card')).toHaveLength(0)
    })
  })

  describe('Exploration actions', () => {
    const startExploration = {
      action_type: 'start_exploration',
      duration_hours: 8,
      stimpaks: 5,
      radaways: 3,
      reason: 'Good stats for exploration',
    }

    const prepare = async ({ room_id = null, ...props }: Record<string, unknown> = {}) => {
      vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockSendDwellerToWasteland.mockResolvedValue({})
      seedDwellers(dweller({ age_group: 'adult', room_id: room_id as string | null }))
      const wrapper = await mounted(props)
      await send(wrapper, 'Explore', { response: 'Ready!', action_suggestion: startExploration })
      return wrapper
    }

    it('renders the start-exploration card', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Go explore', {
        response: 'I want to explore the wasteland!',
        happiness_impact: { delta: 2, reason_text: 'Adventurous' },
        action_suggestion: {
          action_type: 'start_exploration',
          duration_hours: 4,
          stimpaks: 2,
          radaways: 1,
          reason: 'High endurance makes them ideal for exploration',
        },
      })

      const card = wrapper.get('.action-suggestion-card')
      expect(card.text()).toContain('Suggested Action')
      expect(card.text()).toContain('Explore wasteland for 4h')
      expect(card.text()).toContain('High endurance makes them ideal for exploration')
    })

    it('opens the prefilled modal and releases the room only on departure confirm', async () => {
      const unassignSpy = stubManagement('unassignDwellerFromRoom')
      const wrapper = await prepare({ room_id: 'room-456' })

      // Opening presents the modal with the suggestion's plan; nothing is sent
      // and the worker keeps their room until the departure is confirmed.
      await confirmAction(wrapper)
      expect(mockSendDwellerToWasteland).not.toHaveBeenCalled()
      expect(unassignSpy).not.toHaveBeenCalled()
      expect(wrapper.get('.duration-button.active').text()).toBe('8h')
      expect(wrapper.text()).toContain('5 / 10')
      expect(wrapper.text()).toContain('3 / 10')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)

      await wrapper.get('.modal-button.confirm').trigger('click')
      await flushPromises()

      expect(unassignSpy).toHaveBeenCalledWith('dweller-123')
      expect(mockSendDwellerToWasteland).toHaveBeenCalledWith(
        'vault-123',
        'dweller-123',
        8,
        5,
        3,
        undefined
      )
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('refuses to open the modal for an underage dweller', async () => {
      seedDwellers(dweller({ age_group: 'child' }))
      const wrapper = await mounted()
      await send(wrapper, 'Go explore', explorationReply({ response: 'Can I explore?' }))

      await confirmAction(wrapper)

      expect(mockToast.error).toHaveBeenCalledWith('Test Dweller is too young for the wasteland')
      expect(mockSendDwellerToWasteland).not.toHaveBeenCalled()
      expect(wrapper.find('.duration-button').exists()).toBe(false)
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
    })

    it('keeps the card when the send modal is cancelled', async () => {
      const wrapper = await prepare()

      await confirmAction(wrapper)
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)

      await wrapper.get('.modal-button.cancel').trigger('click')
      await flushPromises()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
      expect(mockSendDwellerToWasteland).not.toHaveBeenCalled()
    })

    it('does not release the room twice while a send is in flight', async () => {
      let resolveDispatch: (value: unknown) => void = () => {}
      mockSendDwellerToWasteland.mockReturnValue(
        new Promise((resolve) => {
          resolveDispatch = resolve
        })
      )
      const unassignSpy = stubManagement('unassignDwellerFromRoom')
      seedDwellers(dweller({ room_id: 'room-456' }))
      vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue({} as any)
      const wrapper = await mounted()
      await send(wrapper, 'Go explore', {
        response: 'Leaving my post!',
        action_suggestion: explorationReply().action_suggestion,
      })

      await confirmAction(wrapper)
      await wrapper.get('.modal-button.confirm').trigger('click')
      await flushPromises()
      expect(unassignSpy).toHaveBeenCalledTimes(1)

      await wrapper.get('.modal-button.confirm').trigger('click')
      await flushPromises()
      expect(unassignSpy).toHaveBeenCalledTimes(1)

      resolveDispatch({})
      await flushPromises()
    })

    it('reassigns the original room and keeps the card when the send fails', async () => {
      const management = useDwellerStore().management
      const unassignSpy = stubManagement('unassignDwellerFromRoom')
      const assignSpy = vi.spyOn(management, 'assignDwellerToRoom').mockResolvedValue({} as any)
      seedDwellers(dweller({ room_id: 'room-456' }))
      vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockSendDwellerToWasteland.mockRejectedValue(new Error('dispatch failed'))
      const wrapper = await mounted()
      await send(wrapper, 'Go explore', {
        response: 'Leaving my post!',
        action_suggestion: explorationReply().action_suggestion,
      })

      await openSendModal(wrapper)

      expect(unassignSpy).toHaveBeenCalledWith('dweller-123')
      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'room-456')
      expect(mockToast.error).toHaveBeenCalledWith('Failed to send dweller to wasteland')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
    })

    it('renders the recall card', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'How are you doing out there?', {
        response: 'I miss home...',
        happiness_impact: { delta: -1, reason_text: 'Homesick' },
        action_suggestion: {
          action_type: 'recall_exploration',
          exploration_id: 'exploration-999',
          reason: 'Dweller wants to return',
        },
      })

      const card = wrapper.get('.action-suggestion-card')
      expect(card.text()).toContain('Recall from wasteland')
      expect(card.text()).toContain('Dweller wants to return')
    })

    it.each([
      { progress: 50, expected: 'recallDweller' },
      { progress: 100, expected: 'completeExploration' },
    ])('$expected a recall confirmed at $progress% progress', async ({ progress, expected }) => {
      vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockFetchExplorationProgress.mockResolvedValue({ progress_percentage: progress })
      mockRecallDweller.mockResolvedValue({})
      mockCompleteExploration.mockResolvedValue({})
      const wrapper = await mounted()
      await send(wrapper, 'Come back', {
        response: 'Please bring me back!',
        action_suggestion: {
          action_type: 'recall_exploration',
          exploration_id: 'exploration-999',
          reason: 'Low health',
        },
      })

      await confirmAction(wrapper)

      expect(mockFetchExplorationProgress).toHaveBeenCalledWith('exploration-999')
      if (expected === 'recallDweller') {
        expect(mockRecallDweller).toHaveBeenCalledWith('exploration-999')
        expect(mockCompleteExploration).not.toHaveBeenCalled()
      } else {
        expect(mockCompleteExploration).toHaveBeenCalledWith('exploration-999')
        expect(mockRecallDweller).not.toHaveBeenCalled()
      }
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })
  })

  describe('Map intel', () => {
    const discoveries = [{ location_id: 'place-old-north', name: 'Old North Church' }]

    it('renders intel from a reply beside the dweller message', async () => {
      const wrapper = await mounted()
      await send(wrapper, 'Tell me about Boston.', {
        response: 'I remember the old roads.',
        unlocked_places: discoveries,
      })

      const indicator = wrapper.get('.map-discovery-indicator')
      expect(indicator.text()).toContain('1')
      expect(indicator.attributes('title')).toBe('Map intel: Old North Church unlocked')
      expect(wrapper.get('.map-discovery-link').attributes('href')).toBe(
        '/vault/vault-123/map?place=place-old-north'
      )
    })

    it('renders intel from a streamed response', async () => {
      mockWsState.value = 'connected'
      const wrapper = await mounted()
      await wrapper.get('.chat-input-field').setValue('What places do you know?')
      await wrapper.get('.chat-send-btn').trigger('click')
      await flushPromises()

      mockWebSocketHandlers['token'][0]({ text: 'Try the old overpass.' })
      mockWebSocketHandlers['done'][0]({
        dweller_message_id: 'msg-stream-discovery',
        happiness_impact: null,
        action_suggestion: null,
        unlocked_places: [{ location_id: 'place-rivet-city', name: 'Rivet City' }],
      })
      await flushPromises()

      expect(wrapper.get('.map-discovery-indicator').attributes('title')).toBe(
        'Map intel: Rivet City unlocked'
      )
      expect(wrapper.get('.map-discovery-link').attributes('href')).toBe(
        '/vault/vault-123/map?place=place-rivet-city'
      )
    })
  })

  describe('WebSocket streaming', () => {
    beforeEach(() => {
      mockWsState.value = 'connected'
    })

    const startStream = async (wrapper: VueWrapper, text: string) => {
      await wrapper.get('.chat-input-field').setValue(text)
      await wrapper.get('.chat-send-btn').trigger('click')
      await flushPromises()
    }

    it('streams tokens over the socket instead of posting', async () => {
      const wrapper = await mounted()
      await startStream(wrapper, 'Hello stream')

      expect(mockSendMessage).toHaveBeenCalledWith('Hello stream', false)
      expect(apiClient.post).not.toHaveBeenCalled()
      const messages = wrapper.findAll('.message-wrapper')
      expect(messages).toHaveLength(1)
      expect(messages[0].text()).toContain('Hello stream')
      expect(wrapper.find('.typing-indicator').exists()).toBe(true)

      mockWebSocketHandlers['token'][0]({ text: 'Hel' })
      await wrapper.vm.$nextTick()
      mockWebSocketHandlers['token'][0]({ text: 'lo' })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.message-wrapper')).toHaveLength(2)
      expect(wrapper.findAll('.message-wrapper')[1].text()).toContain('Hello')

      mockWebSocketHandlers['done'][0](wsReply('msg-stream-1', ''))
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.typing-indicator').exists()).toBe(false)
    })

    it('attaches the done payload happiness and suggestion', async () => {
      const wrapper = await mounted()
      await startStream(wrapper, 'Stream with metadata')

      mockWebSocketHandlers['token'][0]({ text: 'Great!' })
      await wrapper.vm.$nextTick()
      mockWebSocketHandlers['done'][0]({
        ...wsReply('msg-stream-2', '', {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength',
        }),
        happiness_impact: { delta: 5, reason_text: 'Positive conversation' },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.get('.happiness-indicator').text()).toContain('+5')
      expect(wrapper.get('.action-suggestion-card').text()).toContain('Train strength')
    })

    it('marks the message failed when the stream errors', async () => {
      const wrapper = await mounted()
      await startStream(wrapper, 'Trigger error')

      mockWebSocketHandlers['error'][0]({ detail: 'AI quota exceeded' })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.typing-indicator').exists()).toBe(false)
      expect(wrapper.text()).toContain('AI quota exceeded')
      expect(wrapper.get('.message-error').attributes()).toMatchObject({
        role: 'alert',
        'aria-live': 'polite',
      })
    })

    it('retries a failed message', async () => {
      const wrapper = await mounted()
      await startStream(wrapper, 'Status report')

      mockWebSocketHandlers['error'].at(-1)!({ detail: 'Connection lost' })
      await flushPromises()
      await wrapper.get('.message-error button').trigger('click')
      await flushPromises()

      expect(mockSendMessage).toHaveBeenCalledTimes(2)
    })
  })

  describe('AI budget readiness', () => {
    it('shows the remaining budget once usage has loaded', () => {
      useProfileStore().$patch({
        aiUsageStats: {
          all_time: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
          current_month: { prompt_tokens: 250, completion_tokens: 100, total_tokens: 350 },
          month: '2026-08',
          quota_limit: 1000,
          quota_used: 350,
          quota_remaining: 650,
          quota_percentage: 35,
          quota_warning: false,
          quota_exceeded: false,
          reset_date: '2026-09-01',
          by_operation: [],
          chat_heavy: false,
        },
      })

      expect(mountChat().get('.chat-budget-status').text()).toContain('650 tokens remaining')
    })
  })

  describe('Dead dweller read-only chat', () => {
    it.each([false, true])(
      'disables the composer for a dead dweller (permanently dead: %s) and never sends',
      async (permanently) => {
        const wrapper = await mounted({ isDead: true, isPermanentlyDead: permanently })

        expect(wrapper.get('.dead-notice').text()).toContain('The dead cannot reply')
        expect((wrapper.get('.chat-input-field').element as HTMLInputElement).disabled).toBe(true)
        expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(true)
        expect(wrapper.find('.dead-revive-btn').exists()).toBe(!permanently)
        expect(wrapper.text().includes('Permanently dead')).toBe(permanently)

        await wrapper.get('.chat-input-field').setValue('Anyone there?')
        await wrapper.get('.chat-send-btn').trigger('click')
        await flushPromises()
        expect(apiClient.post).not.toHaveBeenCalled()
      }
    )

    it('re-enables the composer after a successful revive', async () => {
      const reviveSpy = vi
        .spyOn(useDwellerDeathStore(), 'reviveDweller')
        .mockResolvedValue({ dweller: { first_name: 'Test' }, caps_spent: 5 } as any)
      const wrapper = await mounted({ isDead: true })

      await wrapper.get('.dead-revive-btn').trigger('click')
      await flushPromises()

      expect(reviveSpy).toHaveBeenCalledWith('dweller-123')
      expect(wrapper.find('.dead-notice').exists()).toBe(false)
      expect((wrapper.get('.chat-input-field').element as HTMLInputElement).disabled).toBe(false)

      await wrapper.get('.chat-input-field').setValue('Back among the living')
      expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(false)
    })

    it('leaves a live dweller with an enabled composer', async () => {
      const wrapper = await mounted()

      expect(wrapper.find('.dead-notice').exists()).toBe(false)
      expect((wrapper.get('.chat-input-field').element as HTMLInputElement).disabled).toBe(false)

      await wrapper.get('.chat-input-field').setValue('Hello')
      expect((wrapper.get('.chat-send-btn').element as HTMLButtonElement).disabled).toBe(false)
    })
  })
})
