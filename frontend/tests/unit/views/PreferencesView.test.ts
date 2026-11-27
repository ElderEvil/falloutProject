import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
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

/** A profile whose notification digest can be toggled per category. */
const notificationProfile = (): UserProfile => ({
  ...mockProfile,
  preferences: { notifications: { version: 1, disabled_categories: [] } },
})

const switchByLabel = (wrapper: VueWrapper, label: string) =>
  wrapper.find(`button[role="switch"][aria-label="${label}"]`)

const activePanel = (wrapper: VueWrapper) =>
  wrapper.get('[role="tabpanel"][data-state="active"]').text()

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

  /** Mount with the standard stubs and wait for the next tick. */
  async function mountView(stubs: Record<string, unknown> = {}, settle = false) {
    const wrapper = mount(PreferencesView, {
      global: {
        plugins: [router],
        stubs: { SidePanel: true, Icon: true, PageNavigation: true, ...stubs },
      },
    })
    if (settle) await flushPromises()
    return wrapper
  }

  /** Route to a tab first, then mount — the view reads the tab from the query. */
  async function mountAt(query: string, stubs: Record<string, unknown> = {}) {
    await router.push(`/preferences${query}`)
    return mountView(stubs)
  }

  it.each([
    ['sound', 'Sound Enabled'],
    ['notifications', 'Notification Preferences'],
    ['gameplay', 'Automatically pause when an incident starts'],
  ])('opens a direct link to %s', async (tab, text) => {
    const wrapper = await mountAt(`?tab=${tab}`)

    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe(
      tab.charAt(0).toUpperCase() + tab.slice(1)
    )
    expect(activePanel(wrapper)).toContain(text)
    expect(activePanel(wrapper)).not.toContain('Color Theme')
    wrapper.unmount()
  })

  it('keeps other query parameters when switching tabs and follows route changes', async () => {
    const wrapper = await mountAt('?vault=vault-123')

    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Sound')!
      .trigger('mousedown')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ vault: 'vault-123', tab: 'sound' })
    expect(activePanel(wrapper)).toContain('Sound Enabled')

    await router.replace('/preferences?tab=gameplay')
    await flushPromises()
    expect(activePanel(wrapper)).toContain('Resume the guide')
    expect(activePanel(wrapper)).toContain('Replay orientation')
    wrapper.unmount()
  })

  it('falls back to Appearance for an unknown tab', async () => {
    const wrapper = await mountAt('?tab=unknown')

    expect(wrapper.get('[role="tab"][aria-selected="true"]').text()).toBe('Appearance')
    expect(activePanel(wrapper)).toContain('Color Theme')
    wrapper.unmount()
  })

  it('shows saved volume levels but disables audio controls while muted', async () => {
    audioManager.setMuted(true)
    const wrapper = await mountAt('?tab=sound')

    const sliders = wrapper.findAllComponents({ name: 'Slider' })
    expect(sliders).toHaveLength(4)
    for (const slider of sliders) expect(slider.props('disabled')).toBe(true)
    expect(switchByLabel(wrapper, 'Toggle incident alarm').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('provides one-percent volume adjustments', async () => {
    audioManager.setMuted(false)
    const wrapper = await mountAt('?tab=sound')

    const sliders = wrapper.findAllComponents({ name: 'Slider' })
    expect(sliders).toHaveLength(4)
    for (const slider of sliders) expect(slider.props('step')).toBe(0.01)
    audioManager.setMuted(true)
    wrapper.unmount()
  })

  it('toggles the incident alarm independently of the master switch', async () => {
    audioManager.setMuted(false)
    audioManager.setAlarmEnabled(true)
    const wrapper = await mountAt('?tab=sound')

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
    useProfileStore().profile = { ...mockProfile, preferences: {} }
    const wrapper = await mountAt('?tab=gameplay')

    const toggle = switchByLabel(wrapper, 'Automatically pause when an incident starts')
    expect(toggle.attributes('aria-checked')).toBe('false')

    await toggle.trigger('click')
    await flushPromises()

    expect(useProfileStore().profile?.preferences?.pause_on_incident).toBe(true)
    expect(toggle.attributes('aria-checked')).toBe('true')
  })

  it('passes the persisted selection to the vault sidebar after a refresh', async () => {
    useVaultStore().selectedVaultId = 'vault-123'

    const wrapper = await mountView({
      SidePanel: {
        props: ['vaultId'],
        template: '<div data-testid="side-panel" :data-vault="vaultId" />',
      },
    })

    expect(wrapper.get('[data-testid="side-panel"]').attributes('data-vault')).toBe('vault-123')
  })

  it('renders the grouped preferences page', async () => {
    useProfileStore().profile = mockProfile
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Preferences')
    expect(wrapper.text()).toContain('Appearance')
    expect(activePanel(wrapper)).not.toContain('Notification Preferences')
    expect(activePanel(wrapper)).not.toContain('Incident preparation')
    expect(wrapper.text()).toContain('Sound')
  })

  it('preserves both changes on rapid consecutive toggles', async () => {
    useProfileStore().profile = notificationProfile()
    const wrapper = await mountAt('?tab=notifications')

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
    useProfileStore().profile = notificationProfile()
    vi.mocked(axios.put).mockRejectedValueOnce(new Error('Network error'))
    const wrapper = await mountAt('?tab=notifications')

    await switchByLabel(wrapper, 'Disable Dweller Advancement').trigger('click')
    await flushPromises()

    expect(switchByLabel(wrapper, 'Disable Dweller Advancement').exists()).toBe(true)
    const { toasts } = useToast()
    expect(toasts.value.some((toast) => toast.variant === 'error')).toBe(true)
  })

  it('toggles from a click on the row label text', async () => {
    useProfileStore().profile = notificationProfile()
    const wrapper = await mountAt('?tab=notifications')

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

  it('saves theme changes from the shared picker', async () => {
    useProfileStore().profile = mockProfile
    const wrapper = await mountView()

    await wrapper.get('[aria-label="Select Fallout: New Vegas — Amber Terminal"]').trigger('click')
    await flushPromises()

    expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', {
      preferences: { theme: 'fnv' },
    })
  })

  it('selects glow intensity through the toggle group', async () => {
    useProfileStore().profile = mockProfile
    const wrapper = await mountView()

    await wrapper.find('[aria-label="Set glow to Strong"]').trigger('click')

    expect(wrapper.find('[aria-label="Set glow to Strong"]').attributes('aria-pressed')).toBe(
      'true'
    )
    expect(wrapper.find('[aria-label="Set glow to Normal"]').attributes('aria-pressed')).toBe(
      'false'
    )
  })

  it('starts the colourful-badges switch on and flips it off', async () => {
    useProfileStore().profile = mockProfile
    const wrapper = await mountView()

    const switchButton = wrapper.find('button#colourful-badges')
    // Badges stay tinted by default; the toggle exists to go back to mono.
    expect(wrapper.find('label[for="colourful-badges"]').text()).toContain('Colourful Badges')
    expect(switchButton.attributes('aria-checked')).toBe('true')

    await switchButton.trigger('click')

    expect(switchButton.attributes('aria-checked')).toBe('false')
  })

  it('starts the map-group-colors switch off and flips it on', async () => {
    useProfileStore().profile = mockProfile
    const wrapper = await mountView()

    const switchButton = wrapper.find('button#map-group-colors')
    // The map reads purpose-first by default; family tints are opt-in.
    expect(wrapper.find('label[for="map-group-colors"]').text()).toContain('Colourful Map Markers')
    expect(switchButton.attributes('aria-checked')).toBe('false')

    await switchButton.trigger('click')

    expect(switchButton.attributes('aria-checked')).toBe('true')
  })
})
