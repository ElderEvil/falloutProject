import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import SettingsView from '@/modules/profile/views/SettingsView.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'

// Settings is reachable without a loaded vault (the back nav falls back to `/`),
// so the balance fetch failing must not block rendering the page shell.
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn().mockRejectedValue(new Error('offline')),
  },
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRoute: () => ({ path: '/settings', params: {}, meta: {} }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('shows the vault sidebar when a vault is loaded', async () => {
    useVaultStore().activeVaultId = 'vault-123'

    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Game navigation panel"]').exists()).toBe(true)
  })

  it('keeps the vault sidebar after a refresh (persisted selection, no active vault)', async () => {
    useVaultStore().selectedVaultId = 'vault-123'

    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Game navigation panel"]').exists()).toBe(true)
  })

  it('does not show an empty vault sidebar without a loaded vault', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Game navigation panel"]').exists()).toBe(false)
  })
})
