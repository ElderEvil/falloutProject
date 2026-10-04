import { beforeEach, describe, expect, it, vi } from 'vitest'
import { config, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerChatModal from '@/modules/chat/components/DwellerChatModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// The modal composes shadcn primitives; stub them so the suite stays context-free.
const DialogStub = {
  name: 'Dialog',
  props: ['open'],
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

const fakeDweller = {
  id: 'dweller-1',
  first_name: 'Amata',
  last_name: 'Almodovar',
  status: 'idle',
  thumbnail_url: 'http://example.com/thumb.png',
  age_group: 'adult',
  vault: { id: 'vault-1' },
  room: { name: 'Power Plant' },
} as unknown as Dweller

describe('DwellerChatModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const vaultStore = useVaultStore()
    vaultStore.activeVaultId = 'vault-1'
    vaultStore.selectedVaultId = 'vault-1'
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
    expect(useVaultStore().activeVaultId).toBe('vault-1')
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

  it('updates the chat username when the authenticated user loads', async () => {
    const authStore = useAuthStore()
    authStore.user = null
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(fakeDweller)

    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.findComponent(DwellerChatStub).props('username')).toBe('User')

    authStore.user = { id: 'user-1', username: 'Overseer' }
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(DwellerChatStub).props('username')).toBe('Overseer')
  })

  it('does not switch the selected vault when chatting with a dweller from another vault', async () => {
    const vaultStore = useVaultStore()
    const ensureVaultLoaded = vi.spyOn(vaultStore, 'ensureVaultLoaded')
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue({
      ...fakeDweller,
      vault: { ...fakeDweller.vault!, id: 'vault-2' },
    })

    mountModal()
    await flushPromises()

    expect(ensureVaultLoaded).not.toHaveBeenCalled()
    expect(vaultStore.activeVaultId).toBe('vault-1')
    expect(vaultStore.selectedVaultId).toBe('vault-1')
  })

  it('shows the unavailable state when the dweller cannot be fetched', async () => {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(null)

    const wrapper = mountModal()
    await flushPromises()

    expect(wrapper.text()).toContain('Dweller information unavailable.')
    expect(wrapper.findComponent(DwellerChatStub).exists()).toBe(false)
  })

  it('removes loaded chat data when the session ends', async () => {
    const authStore = useAuthStore()
    vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue(fakeDweller)
    const wrapper = mountModal()
    await flushPromises()
    expect(wrapper.findComponent(DwellerChatStub).exists()).toBe(true)

    authStore.token = null
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(DwellerChatStub).exists()).toBe(false)
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('removes loaded chat data when another user signs in', async () => {
    const authStore = useAuthStore()
    vi.spyOn(useDwellerStore().filter, 'fetchDwellerDetails').mockResolvedValue(fakeDweller)
    const wrapper = mountModal()
    await flushPromises()

    authStore.user = { id: 'user-2', username: 'Another Overseer' }
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(DwellerChatStub).exists()).toBe(false)
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
