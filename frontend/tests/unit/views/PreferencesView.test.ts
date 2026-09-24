import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PreferencesView from '@/modules/profile/views/PreferencesView.vue'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useToast } from '@/core/composables/useToast'
import axios from '@/core/plugins/axios'
import type { UserProfile } from '@/models/profile'

vi.mock('@/core/plugins/axios')

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

const mockProfile: UserProfile = {
  id: 'profile-123',
  user_id: 'user-123',
  bio: 'Test bio',
  avatar_url: 'https://example.com/avatar.jpg',
  preferences: { theme: 'dark' },
  total_dwellers_created: 10,
  total_caps_earned: 500,
  total_explorations: 5,
  total_rooms_built: 8,
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-02T00:00:00Z',
}

function switchByLabel(wrapper: VueWrapper, label: string) {
  return wrapper.find(`button[role="switch"][aria-label="${label}"]`)
}

describe('PreferencesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    const { toasts } = useToast()
    toasts.value = []
    vi.mocked(axios.put).mockImplementation(async (_url, data) => {
      const store = useProfileStore()
      return {
        data: {
          ...(store.profile as UserProfile),
          preferences: (data as { preferences: Record<string, unknown> }).preferences,
        },
      }
    })
  })

  function mountView() {
    return mount(PreferencesView, {
      global: {
        stubs: {
          SidePanel: true,
          Icon: true,
          PageNavigation: true,
        },
      },
    })
  }

  it('renders the grouped preferences page', () => {
    const store = useProfileStore()
    store.profile = mockProfile
    const wrapper = mountView()

    expect(wrapper.text()).toContain('Preferences')
    expect(wrapper.text()).toContain('Appearance')
    expect(wrapper.text()).toContain('Notification Preferences')
    expect(wrapper.text()).toContain('Sound')
  })

  it('preserves both changes on rapid consecutive toggles', async () => {
    const store = useProfileStore()
    store.profile = {
      ...mockProfile,
      preferences: { notifications: { version: 1, disabled_categories: [] } },
    }
    const wrapper = mountView()

    await switchByLabel(wrapper, 'Disable Dweller Advancement').trigger('click')
    await switchByLabel(wrapper, 'Disable Social Activity').trigger('click')
    await flushPromises()

    expect(axios.put).toHaveBeenCalledTimes(2)
    const secondPayload = vi.mocked(axios.put).mock.calls[1]?.[1] as {
      preferences: { notifications: { disabled_categories: string[] } }
    }
    expect(secondPayload.preferences.notifications.disabled_categories).toEqual(
      expect.arrayContaining(['advancement', 'social_activity']),
    )
  })

  it('reverts the toggle and toasts on save failure', async () => {
    const store = useProfileStore()
    store.profile = {
      ...mockProfile,
      preferences: { notifications: { version: 1, disabled_categories: [] } },
    }
    vi.mocked(axios.put).mockRejectedValueOnce(new Error('Network error'))
    const wrapper = mountView()

    await switchByLabel(wrapper, 'Disable Dweller Advancement').trigger('click')
    await flushPromises()

    expect(switchByLabel(wrapper, 'Disable Dweller Advancement').exists()).toBe(true)
    const { toasts } = useToast()
    expect(toasts.value.some((t) => t.variant === 'error')).toBe(true)
  })

  it('toggles from a click on the row label text', async () => {
    const store = useProfileStore()
    store.profile = {
      ...mockProfile,
      preferences: { notifications: { version: 1, disabled_categories: [] } },
    }
    const wrapper = mountView()

    const row = wrapper.findAll('label.setting-row').find((label) => label.text().includes('Crafting'))
    expect(row?.exists()).toBe(true)
    await row?.trigger('click')
    await flushPromises()

    const lastPayload = vi.mocked(axios.put).mock.calls.at(-1)?.[1] as {
      preferences: { notifications: { disabled_categories: string[] } }
    }
    expect(lastPayload.preferences.notifications.disabled_categories).toContain('crafting')
  })

  it('selects glow intensity through the toggle group', async () => {
    const store = useProfileStore()
    store.profile = mockProfile
    const wrapper = mountView()

    await wrapper.find('[aria-label="Set glow to Strong"]').trigger('click')

    expect(wrapper.find('[aria-label="Set glow to Strong"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.find('[aria-label="Set glow to Normal"]').attributes('aria-pressed')).toBe('false')
  })

  it('treats the badge toggle as colourful-on', async () => {
    const store = useProfileStore()
    store.profile = mockProfile
    const wrapper = mountView()

    const switchButton = wrapper.find('button#colourful-badges')
    expect(wrapper.find('label[for="colourful-badges"]').text()).toContain('Colourful Badges')
    expect(switchButton.attributes('aria-checked')).toBe('true')

    await switchButton.trigger('click')

    expect(switchButton.attributes('aria-checked')).toBe('false')
  })
})
