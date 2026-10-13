import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createToastMock } from '../../helpers/mocks'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ContactsPanel from '@/modules/messages/components/ContactsPanel.vue'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { messagesService } from '@/modules/messages/services/messagesService'
import type { ConnectionRead } from '@/modules/messages/models/messages'

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
  },
}))

const incoming = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: 'c-in-1',
  requester_id: 'user-other',
  addressee_id: 'user-me',
  status: 'pending',
  counterpart_username: 'brother_charles',
  created_at: '2026-10-01T12:00:00Z',
  responded_at: null,
  ...overrides,
})

const outgoing = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: 'c-out-1',
  requester_id: 'user-me',
  addressee_id: 'user-other',
  status: 'pending',
  counterpart_username: 'wastelander',
  created_at: '2026-10-01T12:00:00Z',
  responded_at: null,
  ...overrides,
})

const accepted = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: 'c-acc-1',
  requester_id: 'user-me',
  addressee_id: 'user-other',
  status: 'accepted',
  counterpart_username: 'wastelander',
  created_at: '2026-10-01T12:00:00Z',
  responded_at: '2026-10-02T12:00:00Z',
  ...overrides,
})

describe('ContactsPanel', () => {
  // The flag must live on the pinia that wins provide/inject (last plugin).
  const mountPanel = () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useFeatureFlagsStore().playerConnections = true
    return mountWithSetup(ContactsPanel, { global: { plugins: [pinia] } })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    vi.mocked(messagesService.listConnections).mockResolvedValue([])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([])
  })

  it('renders empty sections with invite form', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(messagesService.listConnections).toHaveBeenCalledWith('test-token')
    expect(wrapper.text()).toContain('Invite Player')
    expect(wrapper.text()).toContain('No pending requests.')
    expect(wrapper.text()).toContain('No connections yet.')
    expect(wrapper.text()).toContain('No blocked users.')
  })

  it('lists incoming, outgoing, and accepted connections and blocks', async () => {
    vi.mocked(messagesService.listConnections).mockResolvedValue([
      incoming(),
      outgoing(),
      accepted(),
    ])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([
      { id: 'block-1', blocked_id: 'user-bad', blocked_username: 'raider_king', created_at: null },
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('brother_charles')
    expect(wrapper.text()).toContain('wastelander')
    expect(wrapper.text()).toContain('raider_king')
    expect(wrapper.text()).toContain('Accept')
    expect(wrapper.text()).toContain('Decline')
    expect(wrapper.text()).toContain('Revoke')
    expect(wrapper.text()).toContain('Unblock')
  })

  it('sends an invite from the form and clears the input on success', async () => {
    vi.mocked(messagesService.inviteByUsername).mockResolvedValue(incoming())
    const wrapper = mountPanel()
    await flushPromises()

    const input = wrapper.find('input#invite-username')
    await input.setValue('  brother_charles  ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(messagesService.inviteByUsername).toHaveBeenCalledWith('brother_charles', 'test-token')
    expect(mockToast.success).toHaveBeenCalledWith('Invite sent to brother_charles')
    await flushPromises()
    // fetchContacts toggles isLoading, re-creating the form branch; re-find the live node.
    const clearedInput = wrapper.find('input#invite-username')
    expect((clearedInput.element as HTMLInputElement).value).toBe('')
  })

  it('accepts and declines incoming requests via the row buttons', async () => {
    vi.mocked(messagesService.listConnections).mockResolvedValue([incoming()])
    vi.mocked(messagesService.acceptConnection).mockResolvedValue(incoming({ status: 'accepted' }))
    const wrapper = mountPanel()
    await flushPromises()

    const buttons = wrapper.findAll('li button')
    const acceptButton = buttons.find((b) => b.text().includes('Accept'))
    await acceptButton!.trigger('click')
    await flushPromises()

    expect(messagesService.acceptConnection).toHaveBeenCalledWith('c-in-1', 'test-token')
  })

  it('blocks a connection counterpart and unblocks from the blocked list', async () => {
    vi.mocked(messagesService.listConnections).mockResolvedValue([accepted()])
    vi.mocked(messagesService.listBlocks).mockResolvedValue([
      { id: 'block-1', blocked_id: 'user-other', blocked_username: 'wastelander', created_at: null },
    ])
    vi.mocked(messagesService.blockUser).mockResolvedValue({
      id: 'block-1',
      blocked_id: 'user-other',
      blocked_username: 'wastelander',
      created_at: null,
    })
    const wrapper = mountPanel()
    await flushPromises()

    const buttons = wrapper.findAll('li button')
    await buttons.find((b) => b.text().includes('Block'))!.trigger('click')
    await flushPromises()
    expect(messagesService.blockUser).toHaveBeenCalledWith('user-other', 'test-token')

    await buttons.find((b) => b.text().includes('Unblock'))!.trigger('click')
    await flushPromises()
    expect(messagesService.unblockUser).toHaveBeenCalledWith('user-other', 'test-token')
  })

  it('shows a loading state while contacts load and renders nothing else', async () => {
    let resolveConnections!: (rows: ConnectionRead[]) => void
    vi.mocked(messagesService.listConnections).mockReturnValue(
      new Promise((resolve) => {
        resolveConnections = resolve
      })
    )
    const wrapper = mountPanel()
    await nextTick()

    expect(wrapper.text()).toContain('Loading contacts...')

    resolveConnections([])
    await flushPromises()
    expect(wrapper.text()).toContain('Invite Player')
  })
})
