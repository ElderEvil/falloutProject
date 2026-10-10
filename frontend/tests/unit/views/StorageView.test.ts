import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createIconifyMock, createToastMock } from '../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import StorageView from '@/modules/storage/views/StorageView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

// Mock Iconify so icon-only assertions read the resolved icon name
vi.mock('@iconify/vue', () => createIconifyMock())

// Composables outside the scope of the pets-bucket tests
const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))
vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

const spaceData = {
  used_space: 0,
  max_space: 100,
  available_space: 100,
  utilization_pct: 0,
  stimpack: 0,
  radaway: 0,
}

const petFixture = (overrides: Record<string, unknown> = {}) => ({
  id: 'pet-1',
  name: 'Dogmeat',
  rarity: 'legendary',
  value: 500,
  image_url: '/static/pet_images/dogmeat.png',
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  dweller_id: null,
  storage_id: 'storage-1',
  effect: {
    strength: 0,
    perception: 0,
    endurance: 0,
    charisma: 0,
    intelligence: 0,
    agility: 0,
    luck: 0,
    max_health: 0,
    damage_pct: 0,
    incident_response_pct: 0,
    radiation_resist_pct: 0,
    happiness: 0,
    caps_pct: 0,
    xp_pct: 0,
    training_speed_pct: 0,
  },
  ...overrides,
})

describe('StorageView pets bucket', () => {
  let router: ReturnType<typeof createRouter>
  let vaultStore: ReturnType<typeof useVaultStore>

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())

    // Set token and user in localStorage before initializing the store
    // so useLocalStorage picks them up and doesn't trigger fetchUser.
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'test-user-id',
        username: 'testuser',
        email: 'test@example.com',
      })
    )

    useAuthStore()
    vaultStore = useVaultStore()
    // The vault store would open an SSE stream on load; the pets bucket does
    // not depend on vault state, so keep the load/refresh no-ops.
    vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
    vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue(undefined)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/storage', component: StorageView }],
    })

    vi.clearAllMocks()
  })

  async function mountWith(items: Record<string, unknown[]>) {
    vi.mocked(axios.get).mockImplementation(async (url: string) => {
      if (url.includes('/space')) return { data: spaceData }
      if (url.includes('/items')) return { data: items }
      return { data: {} }
    })

    await router.push('/vault/vault-1/storage')
    await router.isReady()
    const wrapper = mount(StorageView, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }

  const clickTab = async (wrapper: ReturnType<typeof mount>, label: string) => {
    // reka-ui TabsTrigger activates on mousedown (left button), not click
    const trigger = wrapper.findAll('button').find((button) => button.text().includes(label))!
    await trigger.trigger('mousedown')
    await flushPromises()
  }

  it('renders returned pets with name and art in the pets tab', async () => {
    const wrapper = await mountWith({
      weapons: [],
      outfits: [],
      junk: [],
      items: [],
      pets: [
        petFixture(),
        petFixture({ id: 'pet-2', name: 'CX404', image_url: null, rarity: 'rare' }),
      ],
    })

    expect(wrapper.text()).toContain('Pets (2)')

    await clickTab(wrapper, 'Pets')

    // Name + rarity render on the card
    expect(wrapper.text()).toContain('Dogmeat')
    expect(wrapper.text()).toContain('CX404')
    expect(wrapper.text()).toContain('Pet • legendary')

    // Pet art renders as an image when image_url is present
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('dogmeat.png')

    // Pets without art fall back to the paw icon
    const pawIcons = wrapper
      .findAll('.icon-mock')
      .filter((icon) => icon.attributes('data-icon') === 'mdi:paw')
    expect(pawIcons).toHaveLength(1)
  })

  it('shows the pets empty state when no pets are stored', async () => {
    const wrapper = await mountWith({
      weapons: [],
      outfits: [],
      junk: [{ id: 'j1', name: 'Desk Fan', rarity: 'common', value: 10 }],
      items: [],
      pets: [],
    })

    await clickTab(wrapper, 'Pets')

    expect(wrapper.text()).toContain('No pets Found')
    expect(wrapper.text()).not.toContain('Dogmeat')
  })
})
