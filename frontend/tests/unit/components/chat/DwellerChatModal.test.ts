import { beforeEach, describe, expect, it, vi } from 'vitest'
import { config, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerChatModal from '@/modules/chat/components/DwellerChatModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// The modal composes shadcn primitives; stub them so the suite stays context-free.
const DialogStub = {
  name: 'Dialog',
  props: ['open'],
  emits: ['update:open'],
  template: '<div v-if="open" class="mock-modal"><slot /></div>',
}
config.global.stubs = {
  Dialog: DialogStub,
  DialogContent: { template: '<div><slot /></div>' },
  DialogDescription: { template: '<div><slot /></div>' },
  DialogHeader: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<div class="mock-dialog-title"><slot /></div>' },
  TerminalLoadingState: { template: '<div class="mock-loading"><slot /></div>' },
}

// The chat itself is out of scope: the modal's job is to fetch the dweller and
// hand the right props to DwellerChat, which has its own test suite.
const DwellerChatStub = {
  name: 'DwellerChat',
  props: [
    'dwellerId',
    'dwellerName',
    'username',
    'dwellerAvatar',
    'vaultId',
    'dwellerStatus',
    'roomName',
    'dwellerCanExplore',
  ],
  template: '<div class="chat-stub" />',
}

// Vault loading is a side effect the modal mirrors from DwellerChatPage; the
// chat modal test only needs it to be a no-op.
const vaultStoreMock = vi.hoisted(() => ({ activeVaultId: 'vault-1', loadVault: vi.fn() }))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => vaultStoreMock }))

const fakeDweller = {
  id: 'dweller-1',
  first_name: 'Amata',
  last_name: 'Almodovar',
  status: 'idle',
  thumbnail_url: 'http://example.com/thumb.png',
  is_adult: true,
  age_group: 'adult',
  vault: { id: 'vault-1' },
  room: { name: 'Power Plant' },
} as unknown as Dweller

describe('DwellerChatModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vaultStoreMock.activeVaultId = 'vault-1'
    const authStore = useAuthStore()
    authStore.token = 'mock-token'
    authStore.user = { id: 'user-1', username: 'Overseer' }
  })

  function mountModal(props = {}) {
    return mount(DwellerChatModal, {
      props: { dwellerId: 'dweller-1', ...props },
      global: {
        stubs: { DwellerChat: DwellerChatStub },
      },
    })
  }

  it('fetches dweller details and renders DwellerChat with the dweller data', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    const wrapper = mountModal()
    await flushPromises()

    expect(dwellerStore.fetchDwellerDetails).toHaveBeenCalledWith('dweller-1', 'mock-token')
    const chat = wrapper.findComponent(DwellerChatStub)
    expect(chat.exists()).toBe(true)
    expect(chat.props('dwellerId')).toBe('dweller-1')
    expect(chat.props('dwellerName')).toBe('Amata')
    expect(chat.props('username')).toBe('Overseer')
    expect(chat.props('dwellerAvatar')).toBe('http://example.com/thumb.png')
    expect(chat.props('vaultId')).toBe('vault-1')
    expect(chat.props('dwellerStatus')).toBe('idle')
    expect(chat.props('roomName')).toBe('Power Plant')
    expect(chat.props('dwellerCanExplore')).toBe(true)
    expect(vaultStoreMock.loadVault).not.toHaveBeenCalled()
  })

  it('prefers the provided vaultId prop over the dweller-derived one', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    const wrapper = mountModal({ vaultId: 'vault-9' })
    await flushPromises()

    const chat = wrapper.findComponent(DwellerChatStub)
    expect(chat.props('vaultId')).toBe('vault-9')
  })

  it('loads the dweller vault when it differs from the active vault', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({
      ...fakeDweller,
      vault: { ...fakeDweller.vault!, id: 'vault-2' },
    })

    mountModal()
    await flushPromises()

    expect(vaultStoreMock.loadVault).toHaveBeenCalledWith('vault-2', 'mock-token')
  })

  it('emits close when the dialog is dismissed', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })

    const wrapper = mountModal()
    await flushPromises()

    const dialog = wrapper.findComponent(DialogStub)
    dialog.vm.$emit('update:open', false)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('shows the unavailable state when the dweller cannot be fetched', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(null)

    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Dweller information unavailable.')
    expect(wrapper.findComponent(DwellerChatStub).exists()).toBe(false)
  })
})
