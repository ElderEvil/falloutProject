import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerChat from '@/modules/chat/components/DwellerChat.vue'
import * as http from '@/core/plugins/httpClient'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import * as trainingService from '@/modules/progression/services/trainingService'

vi.mock('@/core/plugins/httpClient')

// Mock useAudioRecorder
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

// Mock useChatWebSocket with event handlers
const mockWebSocketHandlers: Record<string, Function[]> = {}
vi.mock('@/core/composables/useWebSocket', () => ({
  useChatWebSocket: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendTypingIndicator: vi.fn(),
    sendMessage: vi.fn(),
    on: (event: string, handler: Function) => {
      if (!mockWebSocketHandlers[event]) {
        mockWebSocketHandlers[event] = []
      }
      mockWebSocketHandlers[event].push(handler)
    },
    state: { value: 'connected' },
  }),
}))

// Mock useToast
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()
const mockToastInfo = vi.fn()

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
    info: mockToastInfo,
  }),
}))

// Mock trainingService
vi.mock('@/modules/progression/services/trainingService', () => ({
  startTraining: vi.fn(),
}))

// Mock useVaultStore
vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({
    activeVault: {},
    activeVaultId: 'vault-123',
  }),
}))

// Mock useRoomStore
const mockRooms = ref([
  {
    id: 'training-room-789',
    name: 'Strength Training',
    category: 'training',
    ability: 'STRENGTH',
    max_capacity: 5,
  },
  {
    id: 'room-456',
    name: 'Power Plant',
    category: 'production',
    ability: null,
    max_capacity: 3,
  },
])
const mockFetchRooms = vi.fn()

vi.mock('@/modules/rooms/stores/room', () => ({
  useRoomStore: () => ({
    get rooms() {
      return mockRooms.value
    },
    fetchRooms: mockFetchRooms,
  }),
}))

const mockSendDwellerToWasteland = vi.fn()
const mockRecallDweller = vi.fn()
const mockCompleteExploration = vi.fn()
const mockFetchExplorationProgress = vi.fn()

vi.mock('@/modules/exploration/stores/exploration', () => ({
  useExplorationStore: () => ({
    sendDwellerToWasteland: mockSendDwellerToWasteland,
    recallDweller: mockRecallDweller,
    completeExploration: mockCompleteExploration,
    fetchExplorationProgress: mockFetchExplorationProgress,
  }),
}))

describe('DwellerChat', () => {
  const defaultProps = {
    dwellerId: 'dweller-123',
    dwellerName: 'Test Dweller',
    username: 'TestUser',
    dwellerAvatar: undefined,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())

    mockSendDwellerToWasteland.mockReset()
    mockRecallDweller.mockReset()
    mockCompleteExploration.mockReset()
    mockFetchExplorationProgress.mockReset()
    mockFetchRooms.mockReset()

    mockRooms.value = [
      {
        id: 'training-room-789',
        name: 'Strength Training',
        category: 'training',
        ability: 'STRENGTH',
        max_capacity: 5,
      },
      {
        id: 'room-456',
        name: 'Power Plant',
        category: 'production',
        ability: null,
        max_capacity: 3,
      },
    ]

    const authStore = useAuthStore()
    authStore.$patch({
      token: 'test-token',
      user: { id: 'user-123', username: 'TestUser' },
    })

    vi.mocked(http.apiGet).mockResolvedValue([])
  })

  const mountComponent = (props = {}) => {
    return mount(DwellerChat, {
      props: { ...defaultProps, ...props },
      global: {
        stubs: {
          Icon: {
            template: '<span class="icon-stub" :data-icon="icon"></span>',
            props: ['icon'],
          },
        },
      },
    })
  }

  const triggerDone = (payload: {
    message_id: string
    response: string
    happiness_impact?: { delta: number; reason_text: string } | null
    action_suggestion?: Record<string, unknown> | null
  }) => {
    mockWebSocketHandlers['done']?.forEach((h) => h(payload))
  }

  describe('Scenario D: Happiness Impact Display', () => {
    it('should render happiness impact badge when response includes happiness_impact', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello there!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-1',
        response: 'Thanks for checking in!',
        happiness_impact: {
          delta: 5,
          reason_text: 'Positive conversation',
        },
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      // Verify happiness indicator is rendered
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('+5')
      expect(happinessIndicator.classes()).toContain('text-green-400')
    })

    it('should render negative happiness impact with red color', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Go away!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-2',
        response: 'That was mean...',
        happiness_impact: {
          delta: -3,
          reason_text: 'Negative conversation',
        },
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      // Verify happiness indicator shows negative
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('-3')
      expect(happinessIndicator.classes()).toContain('text-red-400')
    })

    it('should render neutral happiness impact with gray color', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Status report')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-3',
        response: 'Okay.',
        happiness_impact: {
          delta: 0,
          reason_text: 'Neutral conversation',
        },
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      // Verify happiness indicator shows neutral
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('0')
      expect(happinessIndicator.classes()).toContain('text-gray-400')
    })

    it('should not render happiness indicator when response has no happiness_impact', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hi')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-4',
        response: 'Hello!',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      // Verify no happiness indicator
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(false)
    })
  })

  describe('Scenario D: Action Suggestion with Confirm Button', () => {
    it('should render action suggestion card with confirm button for assign_to_room', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Where would you like to work?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-5',
        response: 'I would love to work in the power plant!',
        happiness_impact: { delta: 2, reason_text: 'Excited about work' },
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-456',
          room_name: 'Power Plant',
          reason: 'High strength makes this a great fit',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Suggested Action')
      expect(actionCard.text()).toContain('Assign to Power Plant')
      expect(actionCard.text()).toContain('High strength makes this a great fit')

      const confirmBtn = wrapper.find('.action-confirm-btn')
      expect(confirmBtn.exists()).toBe(true)
      expect(confirmBtn.text()).toContain('Confirm')
    })

    it('should trigger assignDwellerToRoom when confirm button is clicked for assign_to_room', async () => {
      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Work assignment')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-6',
        response: 'I would love to work there!',
        happiness_impact: { delta: 2, reason_text: 'Happy' },
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-456',
          room_name: 'Power Plant',
          reason: 'Good fit',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'room-456', 'test-token')
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should render action suggestion card with confirm button for start_training', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('What skill do you want to improve?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-7',
        response: 'I want to get stronger!',
        happiness_impact: { delta: 3, reason_text: 'Motivated' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength, needs improvement',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Train strength')
      expect(actionCard.text()).toContain('Low strength, needs improvement')

      const confirmBtn = wrapper.find('.action-confirm-btn')
      expect(confirmBtn.exists()).toBe(true)
    })

    it('should trigger startTraining when confirm button is clicked for start_training', async () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'training-room-789',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train me')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-8',
        response: 'Ready to train!',
        happiness_impact: { delta: 2, reason_text: 'Excited' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Needs strength training',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-789',
        'test-token'
      )
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should not render action suggestion for no_action type', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Just saying hi')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-9',
        response: 'Just chatting.',
        happiness_impact: { delta: 1, reason_text: 'Nice chat' },
        action_suggestion: {
          action_type: 'no_action',
          reason: 'No action needed',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(false)
    })

    it('should dismiss action suggestion when dismiss button is clicked', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Suggest something')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-10',
        response: 'Work suggestion',
        happiness_impact: { delta: 1, reason_text: 'Okay' },
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-123',
          room_name: 'Diner',
          reason: 'Good fit',
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)

      const dismissBtn = wrapper.find('.action-dismiss-btn')
      await dismissBtn.trigger('click')
      await flushPromises()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should not render action suggestion when response has null action_suggestion', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-11',
        response: 'Regular response',
        happiness_impact: { delta: 1, reason_text: 'Good' },
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(false)
    })
  })

  describe('Message Sending', () => {
    it('should send message and display response', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-12',
        response: 'Hello, Overseer!',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const messages = wrapper.findAll('.message-wrapper')
      expect(messages.length).toBe(2)
    })

    it('should disable send button when input is empty', () => {
      const wrapper = mountComponent()

      const sendBtn = wrapper.find('.chat-send-btn')
      expect(sendBtn.classes()).toContain('disabled')
    })

    it('should enable send button when input has text', async () => {
      const wrapper = mountComponent()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello')

      const sendBtn = wrapper.find('.chat-send-btn')
      expect(sendBtn.classes()).not.toContain('disabled')
    })
  })

  describe('Rendering', () => {
    it('should render chat container with dweller name', () => {
      const wrapper = mountComponent()

      expect(wrapper.find('.chat-container').exists()).toBe(true)
      expect(wrapper.find('.identity-name').text()).toBe('Test Dweller')
    })

    it('should show typing indicator when waiting for response', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello')
      await wrapper.find('.chat-send-btn').trigger('click')

      expect(wrapper.find('.typing-indicator').exists()).toBe(true)
    })
  })

  describe('WebSocket Typing Indicator Bug Fix', () => {
    it('should not throw error when typing before WebSocket is connected', async () => {
      // This test reproduces the bug from the error log:
      // "WebSocket not connected, cannot send message"
      // The bug happens when user starts typing before WS connection is established

      const wrapper = mountComponent()
      await flushPromises()

      // Try to type in the input field (this triggers handleTyping via @input event)
      const input = wrapper.find('.chat-input-field')

      // This should NOT throw an error even if WebSocket is not connected yet
      expect(() => {
        input.trigger('input')
      }).not.toThrow()

      // The sendTypingIndicator should either:
      // 1. Not be called if WS is not connected, OR
      // 2. Be called but handle the error gracefully (not throw)
      // With the fix, sendTypingIndicator checks ws.state before sending
    })

    it('should gracefully handle typing when WebSocket connection fails', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Simulate typing - should not crash even if WS fails
      const input = wrapper.find('.chat-input-field')
      await input.setValue('H')
      await input.trigger('input')

      // Component should still be functional
      expect(wrapper.find('.chat-input-field').exists()).toBe(true)
    })
  })

  describe('WebSocket Happiness Update and Action Suggestion - Only Latest Message', () => {
    beforeEach(() => {
      mockWebSocketHandlers['happiness_update'] = []
      mockWebSocketHandlers['action_suggestion'] = []
      mockWebSocketHandlers['done'] = []
    })

    it('should update the correct dweller message by message_id via WebSocket happiness_update', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('First message')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-first',
        response: 'First response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Second message')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-second',
        response: 'Second response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      let messages = wrapper.findAll('.message-wrapper')
      expect(messages.length).toBe(4)

      const happinessHandlers = mockWebSocketHandlers['happiness_update']
      expect(happinessHandlers.length).toBeGreaterThan(0)
      happinessHandlers[0]({
        message_id: 'msg-second',
        happiness_impact: {
          delta: 5,
          reason_text: 'Good conversation',
        },
      })
      await wrapper.vm.$nextTick()

      messages = wrapper.findAll('.message-wrapper')
      const dwellerMessages = messages.filter((m) => m.classes().includes('dweller'))
      expect(dwellerMessages.length).toBe(2)

      const firstDwellerHappiness = dwellerMessages[0].find('.happiness-indicator')
      expect(firstDwellerHappiness.exists()).toBe(false)

      const secondDwellerHappiness = dwellerMessages[1].find('.happiness-indicator')
      expect(secondDwellerHappiness.exists()).toBe(true)
      expect(secondDwellerHappiness.text()).toContain('+5')
    })

    it('should ignore happiness_update without message_id', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Test')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-1',
        response: 'A response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const happinessHandlers = mockWebSocketHandlers['happiness_update']
      happinessHandlers[0]({
        happiness_impact: { delta: 3, reason_text: 'No message_id' },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.happiness-indicator').exists()).toBe(false)
    })

    it('should only update the latest dweller message with action suggestion via WebSocket', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('First message')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-first',
        response: 'First response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Second message')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-second',
        response: 'Second response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      let messages = wrapper.findAll('.message-wrapper')
      expect(messages.length).toBe(4)

      const actionHandlers = mockWebSocketHandlers['action_suggestion']
      expect(actionHandlers.length).toBeGreaterThan(0)
      actionHandlers[0]({
        message_id: 'msg-second',
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-123',
          room_name: 'Power Plant',
          reason: 'Good fit',
        },
      })
      await wrapper.vm.$nextTick()

      messages = wrapper.findAll('.message-wrapper')
      const actionCards = wrapper.findAll('.action-suggestion-card')
      expect(actionCards.length).toBe(1)

      const lastMessage = messages[messages.length - 1]
      expect(lastMessage.find('.action-suggestion-card').exists()).toBe(true)
      expect(lastMessage.text()).toContain('Assign to Power Plant')
    })
  })

  describe('Bug #4: Training Room Auto-Assignment', () => {
    it('should auto-assign dweller to training room before starting training', async () => {
      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train me')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-13',
        response: 'I want to get stronger!',
        happiness_impact: { delta: 3, reason_text: 'Motivated' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength, needs improvement',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'training-room-789', 'test-token')
      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-789',
        'test-token'
      )
    })

    it('should prefer matching-stat training room over generic training room', async () => {
      mockRooms.value = [
        {
          id: 'generic-training',
          name: 'Generic Training',
          category: 'training',
          ability: 'ENDURANCE',
          max_capacity: 5,
        },
        {
          id: 'strength-training',
          name: 'Strength Training',
          category: 'training',
          ability: 'STRENGTH',
          max_capacity: 5,
        },
        {
          id: 'room-456',
          name: 'Power Plant',
          category: 'production',
          ability: null,
          max_capacity: 3,
        },
      ]

      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train strength')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-14',
        response: 'I want to get stronger!',
        happiness_impact: { delta: 3, reason_text: 'Motivated' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength, needs improvement',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'strength-training', 'test-token')
      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'strength-training',
        'test-token'
      )
    })

    it('should fallback to any training room when no stat-matching room available', async () => {
      mockRooms.value = [
        {
          id: 'endurance-training',
          name: 'Endurance Training',
          category: 'training',
          ability: 'ENDURANCE',
          max_capacity: 5,
        },
      ]

      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      dwellerStore.$patch({
        dwellers: [
          {
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train perception')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-15',
        response: 'I want to train perception!',
        happiness_impact: { delta: 2, reason_text: 'Eager' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'perception',
          reason: 'Improve perception',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'endurance-training', 'test-token')
      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'endurance-training',
        'test-token'
      )
    })

    it('should show error when no training rooms available', async () => {
      mockRooms.value = [
        {
          id: 'room-456',
          name: 'Power Plant',
          category: 'production',
          ability: null,
          max_capacity: 3,
        },
      ]

      const dwellerStore = useDwellerStore()

      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train strength')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-16',
        response: 'I want to train strength!',
        happiness_impact: { delta: 2, reason_text: 'Eager' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Improve strength',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockToastError).toHaveBeenCalledWith('No training rooms available')
    })

    it('should show error when all training rooms at capacity', async () => {
      mockRooms.value = [
        {
          id: 'strength-training',
          name: 'Strength Training',
          category: 'training',
          ability: 'STRENGTH',
          max_capacity: 5,
        },
        {
          id: 'endurance-training',
          name: 'Endurance Training',
          category: 'training',
          ability: 'ENDURANCE',
          max_capacity: 3,
        },
      ]

      const dwellerStore = useDwellerStore()

      const strengthFillers = Array.from({ length: 5 }, (_, i) => ({
        id: `dweller-strength-${i}`,
        first_name: `Strength`,
        last_name: `Dweller${i}`,
        room_id: 'strength-training',
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
      }))
      const enduranceFillers = Array.from({ length: 3 }, (_, i) => ({
        id: `dweller-endurance-${i}`,
        first_name: `Endurance`,
        last_name: `Dweller${i}`,
        room_id: 'endurance-training',
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
      }))

      dwellerStore.$patch({
        dwellers: [
          ...strengthFillers,
          ...enduranceFillers,
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train strength')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-17',
        response: 'I want to train strength!',
        happiness_impact: { delta: 2, reason_text: 'Eager' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Improve strength',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockToastError).toHaveBeenCalledWith('No available training rooms (all at capacity)')
    })
  })

  describe('Bug #5: Training works via roomStore when activeVault has no rooms', () => {
    it('should fetch rooms from roomStore and start training when vault has no rooms array', async () => {
      mockRooms.value = []
      mockFetchRooms.mockImplementation(() => {
        mockRooms.value = [
          {
            id: 'training-room-789',
            name: 'Strength Training',
            category: 'training',
            ability: 'STRENGTH',
            max_capacity: 5,
          },
        ]
        return Promise.resolve()
      })

      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-18',
        response: 'Train me!',
        happiness_impact: { delta: 2, reason_text: 'Eager' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Needs training',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockFetchRooms).toHaveBeenCalledWith('vault-123', 'test-token')
      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'training-room-789', 'test-token')
      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-789',
        'test-token'
      )
    })
  })

  describe('Latest-Only Action Suggestion Rendering', () => {
    beforeEach(() => {
      mockWebSocketHandlers['happiness_update'] = []
      mockWebSocketHandlers['action_suggestion'] = []
      mockWebSocketHandlers['done'] = []
    })

    it('should render only ONE action-suggestion-card even if multiple messages have suggestions', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Where do you want to work?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-19',
        response: 'I want to work in the diner!',
        happiness_impact: null,
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-111',
          room_name: 'Diner',
          reason: 'Good fit for diner',
        },
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Changed your mind?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-20',
        response: 'Actually, I prefer the power plant!',
        happiness_impact: null,
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-222',
          room_name: 'Power Plant',
          reason: 'High strength',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCards = wrapper.findAll('.action-suggestion-card')
      expect(actionCards.length).toBe(1)
      expect(actionCards[0].text()).toContain('Power Plant')
      expect(actionCards[0].text()).not.toContain('Diner')
    })

    it('should keep previous actionable suggestion visible when new message has null action_suggestion', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('What should you do?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-21',
        response: 'I should train strength!',
        happiness_impact: { delta: 2, reason_text: 'Motivated' },
        action_suggestion: {
          action_type: 'start_training',
          stat: 'strength',
          reason: 'Low strength needs work',
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
      expect(wrapper.find('.action-suggestion-card').text()).toContain('Train strength')

      await input.setValue('How are you feeling?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-22',
        response: 'Just chatting now.',
        happiness_impact: { delta: 1, reason_text: 'Nice chat' },
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Train strength')
    })

    it('should keep previous actionable suggestion visible when new message has no_action type', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('What do you want?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-23',
        response: 'Send me to explore!',
        happiness_impact: { delta: 3, reason_text: 'Adventurous' },
        action_suggestion: {
          action_type: 'start_exploration',
          duration_hours: 8,
          stimpaks: 3,
          radaways: 2,
          reason: 'Ready for adventure',
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)
      expect(wrapper.find('.action-suggestion-card').text()).toContain('Explore wasteland')

      await input.setValue('Anything else?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-24',
        response: 'Nothing else to say.',
        happiness_impact: null,
        action_suggestion: {
          action_type: 'no_action',
          reason: 'Just conversing',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Explore wasteland')
    })
  })

  describe('WebSocket Message ID Correlation', () => {
    beforeEach(() => {
      mockWebSocketHandlers['happiness_update'] = []
      mockWebSocketHandlers['action_suggestion'] = []
      mockWebSocketHandlers['done'] = []
    })

    it('should update ONLY the message with matching ID when WS emits action_suggestion with message_id', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('First question')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-A',
        response: 'First response without action',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Second question')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-B',
        response: 'Second response without action',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const messages = wrapper.findAll('.message-wrapper')
      expect(messages.length).toBe(4)
      expect(wrapper.findAll('.action-suggestion-card').length).toBe(0)

      const actionHandlers = mockWebSocketHandlers['action_suggestion']
      expect(actionHandlers.length).toBeGreaterThan(0)
      actionHandlers[0]({
        type: 'action_suggestion',
        message_id: 'msg-A',
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-target',
          room_name: 'Target Room',
          reason: 'Targeted update for msg-A only',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCards = wrapper.findAll('.action-suggestion-card')
      expect(actionCards.length).toBe(1)

      const dwellerMessages = messages.filter((m) => m.classes().includes('dweller'))
      expect(dwellerMessages.length).toBe(2)
      expect(dwellerMessages[0].find('.action-suggestion-card').exists()).toBe(true)
      expect(dwellerMessages[0].text()).toContain('Target Room')
      expect(dwellerMessages[1].find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should handle out-of-order WS events - emit for message A after message B exists', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Message A')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-A',
        response: 'Response A - will get delayed WS update',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Message B')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-B',
        response: 'Response B - no action',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      await input.setValue('Message C')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-C',
        response: 'Response C - also no action',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.message-wrapper').length).toBe(6)

      const actionHandlers = mockWebSocketHandlers['action_suggestion']
      actionHandlers[0]({
        type: 'action_suggestion',
        message_id: 'msg-A',
        action_suggestion: {
          action_type: 'start_training',
          stat: 'perception',
          reason: 'Delayed suggestion for message A',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCards = wrapper.findAll('.action-suggestion-card')
      expect(actionCards.length).toBe(1)

      const dwellerMessages = wrapper.findAll('.message-wrapper.dweller')
      expect(dwellerMessages.length).toBe(3)
      expect(dwellerMessages[0].find('.action-suggestion-card').exists()).toBe(true)
      expect(dwellerMessages[0].text()).toContain('Train perception')
      expect(dwellerMessages[1].find('.action-suggestion-card').exists()).toBe(false)
      expect(dwellerMessages[2].find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should ignore WS action_suggestion with unknown message_id', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Test message')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-real',
        response: 'Real response',
        happiness_impact: null,
        action_suggestion: null,
      })
      await wrapper.vm.$nextTick()

      const actionHandlers = mockWebSocketHandlers['action_suggestion']
      actionHandlers[0]({
        type: 'action_suggestion',
        message_id: 'msg-nonexistent',
        action_suggestion: {
          action_type: 'assign_to_room',
          room_id: 'room-123',
          room_name: 'Unknown Room',
          reason: 'Should be ignored',
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.action-suggestion-card').length).toBe(0)
    })
  })

  describe('Exploration Actions from Chat', () => {
    it('should render action suggestion card for start_exploration', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Go explore')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-25',
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
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Suggested Action')
      expect(actionCard.text()).toContain('Explore wasteland for 4h')
      expect(actionCard.text()).toContain('High endurance makes them ideal for exploration')
    })

    it('should call sendDwellerToWasteland when confirm clicked for start_exploration', async () => {
      const dwellerStore = useDwellerStore()
      vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockSendDwellerToWasteland.mockResolvedValue({})

      dwellerStore.$patch({
        dwellers: [
          {
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
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Explore')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-26',
        response: 'Ready to explore!',
        happiness_impact: { delta: 3, reason_text: 'Excited' },
        action_suggestion: {
          action_type: 'start_exploration',
          duration_hours: 8,
          stimpaks: 5,
          radaways: 3,
          reason: 'Good stats for exploration',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockSendDwellerToWasteland).toHaveBeenCalledWith(
        'vault-123',
        'dweller-123',
        8,
        'test-token',
        5,
        3
      )
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should unassign dweller from room before starting exploration', async () => {
      const dwellerStore = useDwellerStore()
      const unassignSpy = vi
        .spyOn(dwellerStore, 'unassignDwellerFromRoom')
        .mockResolvedValue({} as any)
      vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockSendDwellerToWasteland.mockResolvedValue({})

      dwellerStore.$patch({
        dwellers: [
          {
            id: 'dweller-123',
            first_name: 'Test',
            last_name: 'Dweller',
            room_id: 'room-456',
            level: 1,
            happiness: 50,
            strength: 5,
            perception: 5,
            endurance: 5,
            charisma: 5,
            intelligence: 5,
            agility: 5,
            luck: 5,
            status: 'working',
          },
        ],
      })

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Go explore')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-27',
        response: 'Leave my post? Sure!',
        happiness_impact: { delta: 1, reason_text: 'Curious' },
        action_suggestion: {
          action_type: 'start_exploration',
          duration_hours: 4,
          stimpaks: 2,
          radaways: 1,
          reason: 'Wants adventure',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(unassignSpy).toHaveBeenCalledWith('dweller-123', 'test-token')
      expect(mockSendDwellerToWasteland).toHaveBeenCalled()
    })

    it('should render action suggestion card for recall_exploration', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('How are you doing out there?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-28',
        response: 'I miss home...',
        happiness_impact: { delta: -1, reason_text: 'Homesick' },
        action_suggestion: {
          action_type: 'recall_exploration',
          exploration_id: 'exploration-999',
          reason: 'Dweller wants to return',
        },
      })
      await wrapper.vm.$nextTick()

      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Recall from wasteland')
      expect(actionCard.text()).toContain('Dweller wants to return')
    })

    it('should call recallDweller when confirm clicked for recall with progress < 100', async () => {
      const dwellerStore = useDwellerStore()
      vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockFetchExplorationProgress.mockResolvedValue({ progress_percentage: 50 })
      mockRecallDweller.mockResolvedValue({})

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('Come back')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-29',
        response: 'Please bring me back!',
        happiness_impact: { delta: -2, reason_text: 'Tired' },
        action_suggestion: {
          action_type: 'recall_exploration',
          exploration_id: 'exploration-999',
          reason: 'Low health',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockFetchExplorationProgress).toHaveBeenCalledWith('exploration-999', 'test-token')
      expect(mockRecallDweller).toHaveBeenCalledWith('exploration-999', 'test-token')
      expect(mockCompleteExploration).not.toHaveBeenCalled()
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should call completeExploration when confirm clicked for recall with progress >= 100', async () => {
      const dwellerStore = useDwellerStore()
      vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({} as any)
      mockFetchExplorationProgress.mockResolvedValue({ progress_percentage: 100 })
      mockCompleteExploration.mockResolvedValue({})

      const wrapper = mountComponent()
      await flushPromises()

      const input = wrapper.find('.chat-input-field')
      await input.setValue('How was exploring?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      triggerDone({
        message_id: 'msg-30',
        response: 'I found great loot!',
        happiness_impact: { delta: 5, reason_text: 'Successful' },
        action_suggestion: {
          action_type: 'recall_exploration',
          exploration_id: 'exploration-999',
          reason: 'Exploration complete',
        },
      })
      await wrapper.vm.$nextTick()

      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockFetchExplorationProgress).toHaveBeenCalledWith('exploration-999', 'test-token')
      expect(mockCompleteExploration).toHaveBeenCalledWith('exploration-999', 'test-token')
      expect(mockRecallDweller).not.toHaveBeenCalled()
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })
  })
})
