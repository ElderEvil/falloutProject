import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PreferencesView from '@/modules/profile/views/PreferencesView.vue'
import { audioManager } from '@/core/audio/audioManager'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import axios from '@/core/plugins/axios'
import type { UserProfile } from '@/models/profile'

vi.mock('@/core/plugins/axios')

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
  let router: Router

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
    })
    await router.push('/preferences')
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
        plugins: [router],
        stubs: {
          SidePanel: true,
          Icon: true,
          PageNavigation: true,
        },
      },
    })
  }

  it.each([
    ['sound', 'Sound Enabled'],
    ['notifications', 'Notification Preferences'],
    ['gameplay', 'Automatically pause when an incident starts'],
  ])('opens a direct link to %s', async (tab, text) => {
    await router.push(`/preferences?tab=${tab}`)
    const wrapper = mountView()
    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe(
      tab.charAt(0).toUpperCase() + tab.slice(1)
    )
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).toContain(text)
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).not.toContain(
      'Color Theme'
    )
    wrapper.unmount()
  })

  it('keeps other query parameters when switching tabs and follows route changes', async () => {
    await router.push('/preferences?vault=vault-123')
    const wrapper = mountView()
    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Sound')!
      .trigger('mousedown')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ vault: 'vault-123', tab: 'sound' })
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).toContain('Sound Enabled')
    await router.replace('/preferences?tab=gameplay')
    await flushPromises()
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).toContain(
      'Resume the guide'
    )
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).toContain(
      'Replay orientation'
    )
    wrapper.unmount()
  })

  it('falls back to Appearance for an unknown tab', async () => {
    await router.push('/preferences?tab=unknown')
    const wrapper = mountView()
    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe('Appearance')
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).toContain('Color Theme')
    wrapper.unmount()
  })

  it('shows saved volume levels but disables audio controls while muted', async () => {
    audioManager.setMuted(true)
    await router.push('/preferences?tab=sound')
    const wrapper = mountView()
    const sliders = wrapper.findAllComponents({ name: 'Slider' })
    expect(sliders).toHaveLength(4)
    for (const slider of sliders) expect(slider.props('disabled')).toBe(true)
    expect(switchByLabel(wrapper, 'Toggle incident alarm').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('provides one-percent volume adjustments', async () => {
    await router.push('/preferences?tab=sound')
    audioManager.setMuted(false)
    const wrapper = mountView()
    const sliders = wrapper.findAllComponents({ name: 'Slider' })
    expect(sliders).toHaveLength(4)
    for (const slider of sliders) expect(slider.props('step')).toBe(0.01)
    audioManager.setMuted(true)
    wrapper.unmount()
  })

  it('toggles the incident alarm independently of the master switch', async () => {
    await router.push('/preferences?tab=sound')
    audioManager.setMuted(false)
    audioManager.setAlarmEnabled(true)
    const wrapper = mountView()

    const toggle = switchByLabel(wrapper, 'Toggle incident alarm')
    expect(toggle.attributes('aria-checked')).toBe('true')

    await toggle.trigger('click')

    expect(audioManager.alarmEnabled).toBe(false)
    expect(audioManager.muted).toBe(false)
    expect(toggle.attributes('aria-checked')).toBe('false')
    wrapper.unmount()
    audioManager.setAlarmEnabled(true)
    audioManager.setMuted(true)
  })

  it('saves the optional pause-on-incident preference', async () => {
    await router.push('/preferences?tab=gameplay')
    useProfileStore().profile = { ...mockProfile, preferences: {} }
    const wrapper = mountView()
    const toggle = switchByLabel(wrapper, 'Automatically pause when an incident starts')
    expect(toggle.attributes('aria-checked')).toBe('false')
    await toggle.trigger('click')
    await flushPromises()
    expect(useProfileStore().profile?.preferences?.pause_on_incident).toBe(true)
    expect(toggle.attributes('aria-checked')).toBe('true')
  })

  it('passes the persisted selection to the vault sidebar after a refresh', () => {
    useVaultStore().selectedVaultId = 'vault-123'

    const wrapper = mount(PreferencesView, {
      global: {
        plugins: [router],
        stubs: {
          SidePanel: {
            props: ['vaultId'],
            template: '<div data-testid="side-panel" :data-vault="vaultId" />',
          },
          Icon: true,
          PageNavigation: true,
        },
      },
    })

    expect(wrapper.get('[data-testid="side-panel"]').attributes('data-vault')).toBe('vault-123')
  })

  it('renders the grouped preferences page', () => {
    const store = useProfileStore()
    store.profile = mockProfile
    const wrapper = mountView()

    expect(wrapper.text()).toContain('Preferences')
    expect(wrapper.text()).toContain('Appearance')
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).not.toContain(
      'Notification Preferences'
    )
    expect(wrapper.get('[role="tabpanel"][data-state="active"]').text()).not.toContain(
      'Incident preparation'
    )
    expect(wrapper.text()).toContain('Sound')
  })

  it('preserves both changes on rapid consecutive toggles', async () => {
    await router.push('/preferences?tab=notifications')
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
      expect.arrayContaining(['advancement', 'social_activity'])
    )
  })

  it('reverts the toggle and toasts on save failure', async () => {
    await router.push('/preferences?tab=notifications')
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
    await router.push('/preferences?tab=notifications')
    const store = useProfileStore()
    store.profile = {
      ...mockProfile,
      preferences: { notifications: { version: 1, disabled_categories: [] } },
    }
    const wrapper = mountView()

    const row = wrapper
      .findAll('label.setting-row')
      .find((label) => label.text().includes('Crafting'))
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

    expect(wrapper.find('[aria-label="Set glow to Strong"]').attributes('aria-pressed')).toBe(
      'true'
    )
    expect(wrapper.find('[aria-label="Set glow to Normal"]').attributes('aria-pressed')).toBe(
      'false'
    )
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

  it('toggles map marker colours', async () => {
    const store = useProfileStore()
    store.profile = mockProfile
    const wrapper = mountView()

    const switchButton = wrapper.find('button#map-group-colors')
    expect(wrapper.find('label[for="map-group-colors"]').text()).toContain('Colourful Map Markers')
    expect(switchButton.attributes('aria-checked')).toBe('false')

    await switchButton.trigger('click')

    expect(switchButton.attributes('aria-checked')).toBe('true')
  })
})
