import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMessagesStore } from '@/modules/messages/stores/messages'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
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