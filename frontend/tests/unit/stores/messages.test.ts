import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMessagesStore } from '@/modules/messages/stores/messages'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { messagesService } from '@/modules/messages/services/messagesService'
import type { ConnectionRead } from '@/modules/messages/models/messages'

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
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

const connection = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: 'connection-1',
  requester_id: 'user-other',
  addressee_id: 'user-me',
  status: 'pending',
  counterpart_username: 'wastelander',
  created_at: '2026-10-01T12:00:00Z',
  responded_at: null,
  ...overrides,
})

describe('Messages store — contacts', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    useFeatureFlagsStore().playerConnections = true
  })

  it('fetches connections and blocks in parallel', async () => {
    vi.mocked(messagesService.listConnections).mockResolvedValue([connection()])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([
      { id: 'block-1', blocked_id: 'user-bad', blocked_username: 'raider', created_at: null },
    ])
    const store = useMessagesStore()

    await store.fetchContacts()

    expect(messagesService.listConnections).toHaveBeenCalledWith('test-token')
    expect(messagesService.listBlocks).toHaveBeenCalledWith('test-token')
    expect(store.connections).toHaveLength(1)
    expect(store.blocks).toHaveLength(1)
  })

  it('splits pending connections into incoming and outgoing by my user id', async () => {
    vi.mocked(messagesService.listConnections).mockResolvedValue([
      connection({ id: 'c-in', requester_id: 'user-other', addressee_id: 'user-me' }),
      connection({ id: 'c-out', requester_id: 'user-me', addressee_id: 'user-other' }),
      connection({ id: 'c-acc', status: 'accepted', requester_id: 'user-other', addressee_id: 'user-me' }),
    ])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
    const store = useMessagesStore()

    await store.fetchContacts()

    expect(store.incomingRequests.map((c) => c.id)).toEqual(['c-in'])
    expect(store.outgoingRequests.map((c) => c.id)).toEqual(['c-out'])
    expect(store.acceptedConnections.map((c) => c.id)).toEqual(['c-acc'])
  })

  it('invites by username and refreshes the contact lists', async () => {
    vi.mocked(messagesService.inviteByUsername).mockResolvedValue(connection())
    vi.mocked(messagesService.listConnections).mockResolvedValue([])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
    const store = useMessagesStore()

    await store.inviteByUsername('wastelander')

    expect(messagesService.inviteByUsername).toHaveBeenCalledWith('wastelander', 'test-token')
    expect(messagesService.listConnections).toHaveBeenCalled()
  })

  it('accepts and declines incoming requests', async () => {
    const acceptSpy = vi
      .mocked(messagesService.acceptConnection)
      .mockResolvedValue(connection({ status: 'accepted' }))
    vi.mocked(messagesService.declineConnection).mockResolvedValue(undefined)
    vi.mocked(messagesService.listConnections).mockResolvedValue([])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
    const store = useMessagesStore()

    await store.acceptConnection('connection-1')
    expect(acceptSpy).toHaveBeenCalledWith('connection-1', 'test-token')

    await store.declineConnection('connection-1')
    expect(messagesService.declineConnection).toHaveBeenCalledWith('connection-1', 'test-token')
  })

  it('revokes, blocks, and unblocks with refresh after each mutation', async () => {
    vi.mocked(messagesService.revokeConnection).mockResolvedValue(undefined)
    vi.mocked(messagesService.blockUser).mockResolvedValue({
      id: 'block-1',
      blocked_id: 'user-other',
      blocked_username: 'wastelander',
      created_at: null,
    })
    vi.mocked(messagesService.unblockUser).mockResolvedValue(undefined)
    vi.mocked(messagesService.listConnections).mockResolvedValue([])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
    const store = useMessagesStore()

    await store.revokeConnection('connection-1')
    await store.blockUser('user-other')
    await store.unblockUser('user-other')

    expect(messagesService.revokeConnection).toHaveBeenCalledWith('connection-1', 'test-token')
    expect(messagesService.blockUser).toHaveBeenCalledWith('user-other', 'test-token')
    expect(messagesService.unblockUser).toHaveBeenCalledWith('user-other', 'test-token')
    expect(messagesService.listConnections).toHaveBeenCalledTimes(3)
  })

  it('no-ops every action while the player_connections flag is off', async () => {
    useFeatureFlagsStore().playerConnections = false
    const store = useMessagesStore()

    const results = await Promise.all([
      store.fetchContacts(),
      store.inviteByUsername('someone'),
      store.acceptConnection('c-1'),
      store.declineConnection('c-1'),
      store.revokeConnection('c-1'),
      store.blockUser('user-x'),
      store.unblockUser('user-x'),
    ])

    expect(results.every((result) => result === null)).toBe(true)
    expect(messagesService.listConnections).not.toHaveBeenCalled()
    expect(messagesService.listBlocks).not.toHaveBeenCalled()
    expect(messagesService.inviteByUsername).not.toHaveBeenCalled()
    expect(messagesService.blockUser).not.toHaveBeenCalled()
    expect(store.connections).toEqual([])
  })
})
describe('Messages store — conversations and threads', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    useFeatureFlagsStore().playerConnections = true
    vi.mocked(messagesService.getThread).mockResolvedValue([])
    vi.mocked(messagesService.listConversations).mockResolvedValue([])
  })

  it('loads conversations into the list', async () => {
    vi.mocked(messagesService.listConversations).mockResolvedValue([
      {
        counterpart_user_id: 'user-b',
        counterpart_username: 'brother_charles',
        last_message: {
          id: 'm-1',
          sender_user_id: 'user-b',
          recipient_user_id: 'user-me',
          body: 'Any stimpaks?',
          is_request: false,
          created_at: '2026-10-01T12:00:00Z',
        },
        unread_count: 2,
        has_pending_request: false,
      },
    ])
    const store = useMessagesStore()

    await store.loadConversations()

    expect(messagesService.listConversations).toHaveBeenCalledWith('test-token')
    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].counterpart_username).toBe('brother_charles')
  })

  it('openThread loads the thread, marks it active, and polls every 5s', async () => {
    vi.useFakeTimers()
    try {
      vi.mocked(messagesService.getThread).mockResolvedValue([
        {
          id: 'm-1',
          sender_user_id: 'user-b',
          recipient_user_id: 'user-me',
          body: 'hello',
          is_request: false,
          created_at: '2026-10-01T12:00:00Z',
        },
      ])
      const store = useMessagesStore()

      await store.openThread('user-b')

      expect(messagesService.getThread).toHaveBeenCalledWith('user-b', 'test-token')
      expect(store.activeThreadUserId).toBe('user-b')
      expect(store.thread).toHaveLength(1)

      await vi.advanceTimersByTimeAsync(5000)
      expect(messagesService.getThread).toHaveBeenCalledTimes(2)
      expect(messagesService.listConversations).toHaveBeenCalled()

      store.closeThread()
      await vi.advanceTimersByTimeAsync(15000)
      expect(messagesService.getThread).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('closeThread clears the active thread', async () => {
    const store = useMessagesStore()

    await store.openThread('user-b')
    expect(store.activeThreadUserId).toBe('user-b')

    store.closeThread()

    expect(store.activeThreadUserId).toBeNull()
    expect(store.thread).toEqual([])
  })

  it('sendMessage posts to the active thread counterpart and appends the reply', async () => {
    vi.mocked(messagesService.sendMessage).mockResolvedValue({
      id: 'm-2',
      sender_user_id: 'user-me',
      recipient_user_id: 'user-b',
      body: 'Got a box full',
      is_request: false,
      created_at: '2026-10-01T12:01:00Z',
    })
    const store = useMessagesStore()

    await store.openThread('user-b')
    const sent = await store.sendMessage('Got a box full')

    expect(messagesService.sendMessage).toHaveBeenCalledWith('user-b', 'Got a box full', 'test-token')
    expect(sent?.body).toBe('Got a box full')
    expect(store.thread).toHaveLength(1)
    expect(store.thread[0].body).toBe('Got a box full')
  })

  it('sendMessage no-ops without an open thread', async () => {
    const store = useMessagesStore()

    const sent = await store.sendMessage('hello')

    expect(sent).toBeNull()
    expect(messagesService.sendMessage).not.toHaveBeenCalled()
  })

  it('accepts a message request and refreshes conversations and contacts', async () => {
    vi.mocked(messagesService.acceptMessageRequest).mockResolvedValue(connection({ status: 'accepted' }))
    const store = useMessagesStore()

    await store.acceptMessageRequest('user-b')

    expect(messagesService.acceptMessageRequest).toHaveBeenCalledWith('user-b', 'test-token')
    expect(messagesService.listConversations).toHaveBeenCalled()
    expect(messagesService.listConnections).toHaveBeenCalled()
  })

  it('declines a message request and refreshes conversations', async () => {
    vi.mocked(messagesService.declineMessageRequest).mockResolvedValue(undefined)
    const store = useMessagesStore()

    await store.declineMessageRequest('user-b')

    expect(messagesService.declineMessageRequest).toHaveBeenCalledWith('user-b', 'test-token')
    expect(messagesService.listConversations).toHaveBeenCalled()
  })

  it('no-ops thread actions while the player_connections flag is off', async () => {
    useFeatureFlagsStore().playerConnections = false
    const store = useMessagesStore()

    const results = await Promise.all([
      store.loadConversations(),
      store.openThread('user-b'),
      store.sendMessage('hi'),
      store.acceptMessageRequest('user-b'),
      store.declineMessageRequest('user-b'),
    ])

    expect(results.every((result) => result === null)).toBe(true)
    expect(messagesService.listConversations).not.toHaveBeenCalled()
    expect(messagesService.getThread).not.toHaveBeenCalled()
    expect(messagesService.sendMessage).not.toHaveBeenCalled()
    expect(store.conversations).toEqual([])
    expect(store.thread).toEqual([])
  })
})
