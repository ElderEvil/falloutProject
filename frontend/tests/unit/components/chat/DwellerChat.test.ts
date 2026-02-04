import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerChat from '@/modules/chat/components/DwellerChat.vue'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import * as trainingService from '@/modules/progression/services/trainingService'

// Mock axios
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

// Mock useAudioRecorder
vi.mock('@/modules/chat/composables/useAudioRecorder', () => ({
  useAudioRecorder: () => ({
    recordingState: { value: 'inactive' },
    recordingDuration: { value: 0 },
    isRecording: { value: false },
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
    cancelRecording: vi.fn(),
    formatDuration: vi.fn((d: number) => `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`),
  }),
}))

// Mock useChatWebSocket
vi.mock('@/core/composables/useWebSocket', () => ({
  useChatWebSocket: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendTypingIndicator: vi.fn(),
    on: vi.fn(),
  }),
}))

// Mock useToast
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

// Mock trainingService
vi.mock('@/modules/progression/services/trainingService', () => ({
  startTraining: vi.fn(),
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

    // Setup auth store with user
    const authStore = useAuthStore()
    authStore.$patch({
      token: 'test-token',
      user: { id: 'user-123', username: 'TestUser' },
    })

    // Mock empty chat history
    ;(apiClient.get as Mock).mockResolvedValue({ data: [] })
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

  describe('Scenario D: Happiness Impact Display', () => {
    it('should render happiness impact badge when response includes happiness_impact', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with happiness_impact
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Thanks for checking in!',
          happiness_impact: {
            delta: 5,
            reason_text: 'Positive conversation',
          },
          action_suggestion: null,
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello there!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify happiness indicator is rendered
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('+5')
      expect(happinessIndicator.classes()).toContain('text-green-400')
    })

    it('should render negative happiness impact with red color', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with negative happiness_impact
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'That was mean...',
          happiness_impact: {
            delta: -3,
            reason_text: 'Negative conversation',
          },
          action_suggestion: null,
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Go away!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify happiness indicator shows negative
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('-3')
      expect(happinessIndicator.classes()).toContain('text-red-400')
    })

    it('should render neutral happiness impact with gray color', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with zero happiness_impact
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Okay.',
          happiness_impact: {
            delta: 0,
            reason_text: 'Neutral conversation',
          },
          action_suggestion: null,
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Status report')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify happiness indicator shows neutral
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(true)
      expect(happinessIndicator.text()).toContain('0')
      expect(happinessIndicator.classes()).toContain('text-gray-400')
    })

    it('should not render happiness indicator when response has no happiness_impact', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response without happiness_impact
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Hello!',
          happiness_impact: null,
          action_suggestion: null,
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hi')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify no happiness indicator
      const happinessIndicator = wrapper.find('.happiness-indicator')
      expect(happinessIndicator.exists()).toBe(false)
    })
  })

  describe('Scenario D: Action Suggestion with Confirm Button', () => {
    it('should render action suggestion card with confirm button for assign_to_room', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with action_suggestion
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'I would love to work in the power plant!',
          happiness_impact: { delta: 2, reason_text: 'Excited about work' },
          action_suggestion: {
            action_type: 'assign_to_room',
            room_id: 'room-456',
            room_name: 'Power Plant',
            reason: 'High strength makes this a great fit',
          },
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Where would you like to work?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify action suggestion card is rendered
      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Suggested Action')
      expect(actionCard.text()).toContain('Assign to Power Plant')
      expect(actionCard.text()).toContain('High strength makes this a great fit')

      // Verify confirm button exists
      const confirmBtn = wrapper.find('.action-confirm-btn')
      expect(confirmBtn.exists()).toBe(true)
      expect(confirmBtn.text()).toContain('Confirm')
    })

    it('should trigger assignDwellerToRoom when confirm button is clicked for assign_to_room', async () => {
      const dwellerStore = useDwellerStore()
      const assignSpy = vi.spyOn(dwellerStore, 'assignDwellerToRoom').mockResolvedValue({} as any)

      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with assign_to_room action
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'I would love to work there!',
          happiness_impact: { delta: 2, reason_text: 'Happy' },
          action_suggestion: {
            action_type: 'assign_to_room',
            room_id: 'room-456',
            room_name: 'Power Plant',
            reason: 'Good fit',
          },
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Work assignment')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Click confirm button
      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      // Verify store action was called
      expect(assignSpy).toHaveBeenCalledWith('dweller-123', 'room-456', 'test-token')
    })

    it('should render action suggestion card with confirm button for start_training', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with start_training action
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'I want to get stronger!',
          happiness_impact: { delta: 3, reason_text: 'Motivated' },
          action_suggestion: {
            action_type: 'start_training',
            stat: 'strength',
            reason: 'Low strength, needs improvement',
          },
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('What skill do you want to improve?')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify action suggestion card
      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(true)
      expect(actionCard.text()).toContain('Train strength')
      expect(actionCard.text()).toContain('Low strength, needs improvement')

      // Verify confirm button
      const confirmBtn = wrapper.find('.action-confirm-btn')
      expect(confirmBtn.exists()).toBe(true)
    })

    it('should trigger startTraining when confirm button is clicked for start_training', async () => {
      const dwellerStore = useDwellerStore()
      // Add dweller with room_id to the store
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

      // Mock chat response with start_training action
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Ready to train!',
          happiness_impact: { delta: 2, reason_text: 'Excited' },
          action_suggestion: {
            action_type: 'start_training',
            stat: 'strength',
            reason: 'Needs strength training',
          },
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Train me')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Click confirm button
      const confirmBtn = wrapper.find('.action-confirm-btn')
      await confirmBtn.trigger('click')
      await flushPromises()

      // Verify training service was called
      expect(trainingService.startTraining).toHaveBeenCalledWith(
        'dweller-123',
        'training-room-789',
        'test-token'
      )
    })

    it('should not render action suggestion for no_action type', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with no_action
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Just chatting.',
          happiness_impact: { delta: 1, reason_text: 'Nice chat' },
          action_suggestion: {
            action_type: 'no_action',
            reason: 'No action needed',
          },
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Just saying hi')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify no action card is rendered
      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(false)
    })

    it('should dismiss action suggestion when dismiss button is clicked', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response with action_suggestion
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Work suggestion',
          happiness_impact: { delta: 1, reason_text: 'Okay' },
          action_suggestion: {
            action_type: 'assign_to_room',
            room_id: 'room-123',
            room_name: 'Diner',
            reason: 'Good fit',
          },
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Suggest something')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify action card exists
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(true)

      // Click dismiss button
      const dismissBtn = wrapper.find('.action-dismiss-btn')
      await dismissBtn.trigger('click')
      await flushPromises()

      // Verify action card is removed
      expect(wrapper.find('.action-suggestion-card').exists()).toBe(false)
    })

    it('should not render action suggestion when response has null action_suggestion', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response without action_suggestion
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Regular response',
          happiness_impact: { delta: 1, reason_text: 'Good' },
          action_suggestion: null,
        },
      })

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify no action card
      const actionCard = wrapper.find('.action-suggestion-card')
      expect(actionCard.exists()).toBe(false)
    })
  })

  describe('Message Sending', () => {
    it('should send message and display response', async () => {
      const wrapper = mountComponent()
      await flushPromises()

      // Mock chat response
      ;(apiClient.post as Mock).mockResolvedValueOnce({
        data: {
          response: 'Hello, Overseer!',
          happiness_impact: null,
          action_suggestion: null,
        },
      })

      // Type and send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello!')
      await wrapper.find('.chat-send-btn').trigger('click')
      await flushPromises()

      // Verify API was called
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/chat/dweller-123',
        { message: 'Hello!' },
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )

      // Verify messages are displayed
      const messages = wrapper.findAll('.message-wrapper')
      expect(messages.length).toBe(2) // user message + dweller response
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

      // Mock slow response
      ;(apiClient.post as Mock).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: { response: 'Hi' } }), 100))
      )

      // Send message
      const input = wrapper.find('.chat-input-field')
      await input.setValue('Hello')
      await wrapper.find('.chat-send-btn').trigger('click')

      // Typing indicator should be visible
      expect(wrapper.find('.typing-indicator').exists()).toBe(true)
    })
  })
})
