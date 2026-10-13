import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createToastMock } from '../../helpers/mocks'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ConversationsPanel from '@/modules/messages/components/ConversationsPanel.vue'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { messagesService } from '@/modules/messages/services/messagesService'
import type { DirectMessageRead, DirectMessageSummary } from '@/modules/messages/models/messages'

const mockToast = createToastMock()

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    getCurrentUser: vi.fn().mockResolvedValue({
      data: { id: 'user-me', username: 'overseer', is_superuser: true },
    }),
    logout: vi.fn().mockResolvedValue({}),
    refreshToken: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  },
}))
vi.mock('@/modules/messages/services/messagesService', () => ({
  messagesService: {
    listConnections: vi.fn(),
    listBlocks: vi.fn(),
    inviteByUsername: vi.fn(),
    acceptConnection: vi.fn(),
    declineConnection: vi.fn(),
    revokeConnection: vi.fn(),
    blockUser: vi.fn(),
    unblockUser: vi.fn(),
    sendMessage: vi.fn(),
    getThread: vi.fn(),
    listConversations: vi.fn(),
    acceptMessageRequest: vi.fn(),
    declineMessageRequest: vi.fn(),
  },
}))

const message = (overrides: Partial<DirectMessageRead> = {}): DirectMessageRead => ({
  id: 'm-1',
  sender_user_id: 'user-other',
  recipient_user_id: 'user-me',
  body: 'Radiation suits?',
  is_request: false,
  created_at: '2026-10-01T12:00:00Z',
  ...overrides,
})

const conversation = (overrides: Partial<DirectMessageSummary> = {}): DirectMessageSummary => ({
  counterpart_user_id: 'user-other',
  counterpart_username: 'brother_charles',
  last_message: message(),
  unread_count: 0,
  has_pending_request: false,
  ...overrides,
})

describe('ConversationsPanel', () => {
  // The flag must live on the pinia that wins provide/inject (last plugin).
  const mountPanel = () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useFeatureFlagsStore().playerConnections = true
    return mountWithSetup(ConversationsPanel, { global: { plugins: [pinia] } })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    vi.mocked(messagesService.listConversations).mockResolvedValue([])
    vi.mocked(messagesService.getThread).mockResolvedValue([])
    vi.mocked(messagesService.listConnections).mockResolvedValue([])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
  })

  it('renders the conversation list with username, preview, and unread count', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([
      conversation({ unread_count: 3 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('brother_charles')
    expect(wrapper.text()).toContain('Radiation suits?')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('Select a conversation to read messages')
  })

  it('opens a thread on row click and renders the message history', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([conversation()])
    vi.mocked(messagesService.getThread).mockResolvedValue([
      message({ id: 'm-1', sender_user_id: 'user-other', body: 'Still there?' }),
      message({ id: 'm-2', sender_user_id: 'user-me', body: 'Copy that' }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('aside button').trigger('click')
    await flushPromises()

    expect(messagesService.getThread).toHaveBeenCalledWith('user-other', 'test-token')
    expect(wrapper.text()).toContain('Still there?')
    expect(wrapper.text()).toContain('Copy that')
  })

  it('shows message requests with accept/decline and accepts one', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([
      conversation({ has_pending_request: true, last_message: message({ is_request: true }) }),
    ])
    vi.mocked(messagesService.acceptMessageRequest).mockResolvedValue({
      id: 'c-new',
      requester_id: 'user-other',
      addressee_id: 'user-me',
      status: 'accepted',
      counterpart_username: 'brother_charles',
      created_at: '2026-10-01T12:00:00Z',
      responded_at: null,
    })
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Message Requests')
    expect(wrapper.text()).toContain('wants to message you')

    const buttons = wrapper.findAll('button')
    const acceptButton = buttons.find((b) => b.text().includes('Accept'))
    await acceptButton!.trigger('click')
    await flushPromises()

    expect(messagesService.acceptMessageRequest).toHaveBeenCalledWith('user-other', 'test-token')
  })

  it('sends a message from the composer and appends it to the thread', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([conversation()])
    vi.mocked(messagesService.getThread).mockResolvedValue([message()])
    vi.mocked(messagesService.sendMessage).mockResolvedValue(
      message({ id: 'm-9', sender_user_id: 'user-me', body: 'Any stimpaks left?' })
    )
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('aside button').trigger('click')
    await flushPromises()

    const textarea = wrapper.find('textarea#message-composer')
    await textarea.setValue('Any stimpaks left?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(messagesService.sendMessage).toHaveBeenCalledWith(
      'user-other',
      'Any stimpaks left?',
      'test-token'
    )
    expect(wrapper.text()).toContain('Any stimpaks left?')
  })

  it('disables the send button while the draft is empty', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([conversation()])
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.find('aside button').trigger('click')
    await flushPromises()

    const sendButton = wrapper.find('button[aria-label="Send message"]')
    expect(sendButton.attributes('disabled')).toBeDefined()

    await wrapper.find('textarea#message-composer').setValue('hello')
    await flushPromises()
    expect(wrapper.find('button[aria-label="Send message"]').attributes('disabled')).toBeUndefined()
  })
})
