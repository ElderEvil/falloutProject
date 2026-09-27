import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerChatModal from '@/modules/chat/components/DwellerChatModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// Real Reka dialog primitives: this suite proves the visible close control
// actually closes the modal (no dialog stubs — stubbing them would hide
// exactly this class of bug). Only the chat payload and icon are stubbed.
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

vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({
    activeVaultId: 'vault-1',
    loadVault: vi.fn(),
  }),
}))

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

describe('DwellerChatModal header and close', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const authStore = useAuthStore()
    authStore.token = 'mock-token'
    authStore.user = { id: 'user-1', username: 'Overseer' }
    document.body.innerHTML = ''
  })

  function mountModal() {
    const dwellerStore = useDwellerStore().filter
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockImplementation(async (id: string) => {
      dwellerStore.detailedDwellers[id] = fakeDweller
      return fakeDweller
    })
    return mount(DwellerChatModal, {
      props: { dwellerId: 'dweller-1' },
      attachTo: document.body,
      global: {
        stubs: {
          DwellerChat: DwellerChatStub,
          TerminalLoadingState: true,
          Icon: true,
        },
      },
    })
  }

  it('shows the dweller full name in the header', async () => {
    const wrapper = mountModal()
    await flushPromises()

    expect(document.body.textContent).toContain('Amata Almodovar')
    wrapper.unmount()
  })

  it('emits close when the header close button is clicked', async () => {
    const wrapper = mountModal()
    await flushPromises()

    const closeButton = document.body.querySelector(
      'button[aria-label="Close chat"]'
    ) as HTMLButtonElement | null
    expect(closeButton).not.toBeNull()

    closeButton!.click()
    await flushPromises()

    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })
})
