import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '@/modules/profile/views/ProfileView.vue'
import ProfileEditor from '@/modules/profile/components/ProfileEditor.vue'
import { LifeDeathStatistics } from '@/modules/dwellers/components/death'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'
import type { UserProfile } from '@/models/profile'
import type { DeathStatistics } from '@/modules/profile/stores/profile'

vi.mock('@/core/plugins/axios')

// SidePanel requests feature flags on mount; unstubbed, that call would consume the
// `mockRejectedValueOnce` queued for the profile fetch.
vi.mock('@/core/stores/featureFlags', () => ({
  useFeatureFlagsStore: () => ({ worldEvents: false, loaded: true, fetchFlags: vi.fn() }),
}))

const { usePollingMock } = vi.hoisted(() => ({
  usePollingMock: vi.fn(() => ({ pause: vi.fn(), resume: vi.fn(), isActive: { value: false } })),
}))

vi.mock('@/core/composables/usePolling', () => ({
  usePolling: usePollingMock,
}))

vi.mock('@/modules/profile/components/ConnectedAccountsCard.vue', () => ({
  default: { name: 'ConnectedAccountsCard', template: '<div data-testid="connected-accounts" />' },
}))

describe('ProfileView', () => {
  let router: ReturnType<typeof createRouter>
  let authStore: ReturnType<typeof useAuthStore>
  let profileStore: ReturnType<typeof useProfileStore>
  let vaultStore: ReturnType<typeof useVaultStore>
  let wrapper: VueWrapper

  const mockProfile: UserProfile = {
    id: 'profile-123',
    user_id: 'user-123',
    bio: 'Test bio for overseer',
    avatar_url: 'https://example.com/avatar.jpg',
    preferences: { theme: 'dark', notifications: true },
    total_dwellers_created: 10,
    total_caps_earned: 5000,
    total_explorations: 25,
    total_rooms_built: 8,
    total_incidents: 9,
    total_incidents_won: 6,
    total_incidents_lost: 3,
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-02T00:00:00Z',
  }

  const mockDeathStatistics: DeathStatistics = {
    total_dwellers_born: 50,
    total_dwellers_died: 10,
    deaths_by_cause: {
      health: 3,
      radiation: 2,
      incident: 2,
      exploration: 2,
      combat: 1,
    },
    revivable_count: 3,
    permanently_dead_count: 7,
  }

  /** Serve the profile and its death statistics; anything else is a bug. */
  const serveProfile = () =>
    vi.mocked(axios.get).mockImplementation((url: string) => {
      if (url === '/api/v1/users/me/profile') return Promise.resolve({ data: mockProfile })
      if (url === '/api/v1/users/me/profile/statistics') {
        return Promise.resolve({ data: mockDeathStatistics })
      }
      return Promise.reject(new Error('Unknown URL'))
    })

  const mountProfile = () => {
    wrapper = mount(ProfileView, { global: { plugins: [router] } })
    return wrapper
  }

  const mountView = async () => {
    mountProfile()
    await flushPromises()
    return wrapper
  }

  const editButton = () =>
    wrapper.findAll('button').find((button) => button.text().includes('Edit'))

  /** The profile is read-only until the Edit action swaps in ProfileEditor. */
  const openEditor = async () => {
    await editButton()!.trigger('click')
    await flushPromises()
    return wrapper.findComponent(ProfileEditor)
  }

  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())

    authStore = useAuthStore()
    profileStore = useProfileStore()
    vaultStore = useVaultStore()

    authStore.token = 'test-token'
    authStore.user = {
      id: 'user-123',
      email: 'overseer@vault.com',
      username: 'Overseer',
    } as never

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/profile', component: ProfileView },
        { path: '/vault/:id', component: { template: '<div>Vault</div>' } },
      ],
    })

    vi.clearAllMocks()
    usePollingMock.mockReturnValue({ pause: vi.fn(), resume: vi.fn(), isActive: { value: false } })
  })

  it.each([false, true])(
    'shows existing admin destinations only to administrators (%s)',
    async (isSuperuser) => {
      serveProfile()
      authStore.user = { ...authStore.user, is_superuser: isSuperuser } as never
      await mountView()

      expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).toEqual([
        'Dossier',
        'Vault Analytics',
      ])
      expect(wrapper.find('[aria-label="Administration"]').exists()).toBe(isSuperuser)
      expect(wrapper.find('a[href="/admin/ai-settings"]').exists()).toBe(isSuperuser)
      if (isSuperuser) {
        const consoleLink = wrapper.findAll('a').find((link) => link.text() === 'Admin console')!
        expect(new URL(consoleLink.attributes('href')).pathname).toBe('/admin/')
      }
      expect(wrapper.findComponent({ name: 'AISettingsPanel' }).exists()).toBe(false)
      wrapper.unmount()
    }
  )

  it('keeps analytics on its tab and uses quick access only for other screens', async () => {
    serveProfile()
    await mountView()

    expect(
      wrapper
        .findAll('button')
        .some((button) => button.text().includes('View activity and AI usage'))
    ).toBe(false)
    expect(wrapper.find('a[href="/preferences"]').exists()).toBe(true)
    await wrapper
      .findAll('[role="tab"]')
      .find((tab) => tab.text() === 'Vault Analytics')!
      .trigger('mousedown')

    expect(wrapper.get('[aria-label="Vault analytics"]').isVisible()).toBe(true)
    wrapper.unmount()
  })

  describe('Navigation', () => {
    it('returns to the screen the profile was opened from', async () => {
      serveProfile()
      vaultStore.activeVaultId = 'vault-1'
      await router.push('/vault/vault-1')
      await router.push('/profile')
      await router.isReady()

      await mountView()
      await wrapper.find('button[aria-label="Back to Overview"]').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/vault/vault-1')
    })

    it('falls back to the persisted vault after a direct /profile load', async () => {
      serveProfile()
      // Simulate a refresh: the in-memory active vault is unset, but the
      // persisted selection survives.
      vaultStore.activeVaultId = null
      vaultStore.selectedVaultId = 'vault-1'
      await router.push('/profile')
      await router.isReady()

      await mountView()

      expect(wrapper.findComponent(SidePanel).props('vaultId')).toBe('vault-1')
      expect(wrapper.find('a[href="/vault/vault-1"]').exists()).toBe(true)
      expect(wrapper.text()).not.toContain('Vault undefined')

      const backButton = wrapper.findAll('button').find((btn) => btn.text().includes('Back'))
      expect(backButton?.exists()).toBe(true)
      await backButton?.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/vault/vault-1')
    })
  })

  describe('Mounting and loading', () => {
    it('fetches the profile and its statistics on mount, then refreshes on poll', async () => {
      serveProfile()
      await mountView()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile')
      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile/statistics')
      expect(
        vi.mocked(axios.get).mock.calls.filter(([url]) => url === '/api/v1/users/me/profile')
      ).toHaveLength(1)

      const refresh = usePollingMock.mock.calls[0]?.[0]
      expect(refresh).toBeTypeOf('function')
      await refresh?.()

      expect(
        vi.mocked(axios.get).mock.calls.filter(([url]) => url === '/api/v1/users/me/profile')
      ).toHaveLength(2)
    })

    it('shows a loading indicator while fetching the profile', async () => {
      vi.mocked(axios.get).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockProfile }), 100))
      )
      mountProfile()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Loading your profile...')
    })
  })

  describe('Error state', () => {
    it('shows the failure detail with a retry action', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce({
        response: { data: { detail: 'Failed to fetch profile' } },
      })
      await mountView()

      expect(wrapper.text()).toContain('Profile unavailable')
      expect(wrapper.text()).toContain('Failed to fetch profile')
      expect(wrapper.text()).toContain('Retry Connection')
    })

    it('retries fetching the profile when the retry button is clicked', async () => {
      vi.mocked(axios.get)
        .mockRejectedValueOnce({ response: { data: { detail: 'Network error' } } })
        .mockImplementation((url: string) => {
          if (url === '/api/v1/users/me/profile') return Promise.resolve({ data: mockProfile })
          if (url === '/api/v1/users/me/profile/statistics') {
            return Promise.resolve({ data: mockDeathStatistics })
          }
          return Promise.reject(new Error('Unknown URL'))
        })
      await mountView()

      const retryButton = wrapper.findAll('button').find((btn) => btn.text().includes('Retry'))
      await retryButton?.trigger('click')
      await flushPromises()

      // Verify profile was retried and succeeded (error message should be gone)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile')
      expect(wrapper.text()).not.toContain('Profile unavailable')
      expect(wrapper.text()).toContain('User Profile')
    })
  })

  describe('Profile display', () => {
    beforeEach(() => {
      serveProfile()
    })

    it('renders the account identity, bio and avatar', async () => {
      await mountView()

      const text = wrapper.text()
      expect(text).toContain('overseer@vault.com')
      expect(text).toContain('Test bio for overseer')
      const avatar = wrapper.find('img[alt="Profile avatar"]')
      expect(avatar.exists()).toBe(true)
      expect(avatar.attributes('src')).toBe('https://example.com/avatar.jpg')
    })

    it('keeps preferences in their dedicated screen instead of exposing raw JSON', async () => {
      await mountView()

      const prefsText = wrapper.text()
      expect(prefsText).toContain('Preferences')
      expect(prefsText).not.toContain('"theme": "dark"')
    })
  })

  describe('LifeDeathStatistics', () => {
    it('receives the fetched statistics once loaded', async () => {
      serveProfile()
      await mountView()

      const statsComponent = wrapper.findComponent(LifeDeathStatistics)
      expect(statsComponent.props('statistics')).toEqual(mockDeathStatistics)
      expect(statsComponent.props('loading')).toBe(false)
    })
  })

  describe('Edit mode', () => {
    it('swaps the read-only profile for the editor with the current data', async () => {
      serveProfile()
      await mountView()

      const editor = await openEditor()

      expect(editor.exists()).toBe(true)
      expect(editor.props('initialData')).toEqual(mockProfile)
    })

    it('submits the edit and leaves edit mode on success', async () => {
      serveProfile()
      vi.mocked(axios.put).mockResolvedValueOnce({ ...mockProfile, bio: 'Updated bio' })
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'Updated bio' })
      await flushPromises()

      expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', { bio: 'Updated bio' })
      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
    })

    it('cancels edit mode when the editor emits cancel', async () => {
      serveProfile()
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('cancel')
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
    })

    it('stays in edit mode and reports the error if the update fails', async () => {
      serveProfile()
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Validation error' } },
      })
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'Invalid data' })
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(true)
      expect(editor.props('error')).toBe('Validation error')
    })

    it('passes the saving state to the editor', async () => {
      serveProfile()
      vi.mocked(axios.put).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockProfile }), 100))
      )
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'New bio' })
      await wrapper.vm.$nextTick()

      expect(editor.props('loading')).toBe(true)
    })

    it('updates the account email before saving the profile', async () => {
      serveProfile()
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'New bio' }, null, 'new@vault-tec.com')
      await flushPromises()

      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/users/me',
        { email: 'new@vault-tec.com' },
        { _skipErrorNotification: true }
      )
    })

    it('sends username and email in one account request', async () => {
      serveProfile()
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'New bio' }, 'new_name', 'new@vault-tec.com')
      await flushPromises()

      const accountCalls = vi
        .mocked(axios.put)
        .mock.calls.filter(([url]) => url === '/api/v1/users/me')
      expect(accountCalls).toHaveLength(1)
      expect(accountCalls[0]?.[1]).toEqual({
        username: 'new_name',
        email: 'new@vault-tec.com',
      })
    })

    it('ignores a second submit while the first is still saving', async () => {
      serveProfile()
      const updateSpy = vi.spyOn(profileStore, 'updateProfile').mockResolvedValue(undefined)
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'First' })
      editor.vm.$emit('submit', { bio: 'Second' })
      await flushPromises()

      expect(updateSpy).toHaveBeenCalledTimes(1)
    })
  })

  describe('Error clearing', () => {
    it('clears a stale error when entering edit mode', async () => {
      serveProfile()
      await mountView()
      profileStore.error = 'Some previous error'

      await openEditor()

      expect(profileStore.error).toBeNull()
    })

    it('clears the update error when canceling edit mode', async () => {
      serveProfile()
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Update error' } },
      })
      await mountView()

      const editor = await openEditor()
      editor.vm.$emit('submit', { bio: 'Test' })
      await flushPromises()
      editor.vm.$emit('cancel')
      await flushPromises()

      expect(profileStore.error).toBeNull()
    })
  })

  describe('Email verification actions', () => {
    const resendButton = () =>
      wrapper.findAll('button').find((button) => button.text().includes('RESEND EMAIL'))

    it.each([
      [false, true],
      [true, false],
    ])(
      'shows the resend action only for unverified accounts (verified=%s)',
      async (verified, shown) => {
        serveProfile()
        authStore.user = { ...authStore.user, email_verified: verified } as never
        await mountView()

        expect(resendButton() !== undefined).toBe(shown)
      }
    )

    it('resends the verification email when clicked', async () => {
      serveProfile()
      const resendSpy = vi.spyOn(authStore, 'resendVerificationEmail').mockResolvedValue(true)
      await mountView()

      await resendButton()!.trigger('click')
      await flushPromises()

      expect(resendSpy).toHaveBeenCalledOnce()
    })
  })
})
