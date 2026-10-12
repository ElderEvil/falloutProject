import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock } from '../helpers/mocks'
import type { Mock } from 'vitest'
import axios from '@/core/plugins/axios'
import { messagesService } from '@/modules/messages/services/messagesService'
import type { ConnectionRead, UserBlockRead } from '@/modules/messages/models/messages'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

const connection = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: 'connection-1',
  requester_id: 'user-a',
  addressee_id: 'user-b',
  status: 'pending',
  counterpart_username: 'brother_charles',
  created_at: '2026-10-01T12:00:00Z',
  responded_at: null,
  ...overrides,
})

const block = (overrides: Partial<UserBlockRead> = {}): UserBlockRead => ({
  id: 'block-1',
  blocked_id: 'user-c',
  blocked_username: 'raider_king',
  created_at: '2026-10-01T12:00:00Z',
  ...overrides,
})

const TOKEN = 'jwt-token'

const AUTH_HEADERS = expect.objectContaining({
  headers: { Authorization: `Bearer ${TOKEN}` },
})

describe('messagesService connections and blocks', () => {
  const axiosGet = vi.mocked(axios.get) as unknown as Mock
  const axiosPost = vi.mocked(axios.post) as unknown as Mock
  const axiosDelete = vi.mocked(axios.delete) as unknown as Mock

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('invites by username with the bearer header, returning the created connection', async () => {
    axiosPost.mockResolvedValue({ data: connection({ counterpart_username: 'brother_charles' }) })

    const result = await messagesService.inviteByUsername('brother_charles', TOKEN)

    expect(axiosPost).toHaveBeenCalledWith(
      '/api/v1/connections',
      { username: 'brother_charles' },
      AUTH_HEADERS
    )
    expect(result.counterpart_username).toBe('brother_charles')
  })

  it('accepts a connection request, returning the accepted connection', async () => {
    axiosPost.mockResolvedValue({ data: connection({ status: 'accepted' }) })

    const result = await messagesService.acceptConnection('connection-1', TOKEN)

    expect(axiosPost).toHaveBeenCalledWith(
      '/api/v1/connections/connection-1/accept',
      null,
      AUTH_HEADERS
    )
    expect(result.status).toBe('accepted')
  })

  it('declines a connection request', async () => {
    axiosPost.mockResolvedValue({ data: null })

    await messagesService.declineConnection('connection-1', TOKEN)

    expect(axiosPost).toHaveBeenCalledWith(
      '/api/v1/connections/connection-1/decline',
      null,
      AUTH_HEADERS
    )
  })

  it('revokes a connection', async () => {
    axiosDelete.mockResolvedValue({ data: null })

    await messagesService.revokeConnection('connection-1', TOKEN)

    expect(axiosDelete).toHaveBeenCalledWith('/api/v1/connections/connection-1', AUTH_HEADERS)
  })

  it('lists connections', async () => {
    axiosGet.mockResolvedValue({ data: [connection()] })

    const result = await messagesService.listConnections(TOKEN)

    expect(axiosGet).toHaveBeenCalledWith('/api/v1/connections', AUTH_HEADERS)
    expect(result).toHaveLength(1)
  })

  it('blocks a user, returning the block row', async () => {
    axiosPost.mockResolvedValue({ data: block() })

    const result = await messagesService.blockUser('user-c', TOKEN)

    expect(axiosPost).toHaveBeenCalledWith('/api/v1/blocks/user-c', null, AUTH_HEADERS)
    expect(result.blocked_username).toBe('raider_king')
  })

  it('unblocks a user', async () => {
    axiosDelete.mockResolvedValue({ data: null })

    await messagesService.unblockUser('user-c', TOKEN)

    expect(axiosDelete).toHaveBeenCalledWith('/api/v1/blocks/user-c', AUTH_HEADERS)
  })

  it('lists blocks', async () => {
    axiosGet.mockResolvedValue({ data: [block()] })

    const result = await messagesService.listBlocks(TOKEN)

    expect(axiosGet).toHaveBeenCalledWith('/api/v1/blocks', AUTH_HEADERS)
    expect(result).toHaveLength(1)
  })
})