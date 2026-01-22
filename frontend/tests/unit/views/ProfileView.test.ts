import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '@/modules/profile/views/ProfileView.vue'
import ProfileEditor from '@/modules/profile/components/ProfileEditor.vue'
import { LifeDeathStatistics } from '@/modules/dwellers/components/death'
import { useProfileStore } from '@/stores/profile'
import { useAuthStore } from '@/stores/auth'
import axios from '@/core/plugins/axios'
import type { UserProfile } from '@/models/profile'
import type { DeathStatistics } from '@/modules/profile/stores/profile'

vi.mock('@/core/plugins/axios')

describe('ProfileView', () => {
  let router: any
  let authStore: any
  let profileStore: any

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
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-02T00:00:00Z'
  }

  const mockDeathStatistics: DeathStatistics = {
    total_dwellers_born: 50,
    total_dwellers_died: 10,
    deaths_by_cause: {
      health: 3,
      radiation: 2,
      incident: 2,
      exploration: 2,
      combat: 1
    },
    revivable_count: 3,
    permanently_dead_count: 7
  }

  beforeEach(() => {
    // Create fresh Pinia instance for each test
    const pinia = createPinia()
    setActivePinia(pinia)

    authStore = useAuthStore()
    profileStore = useProfileStore()

    authStore.token = 'test-token'
    authStore.user = {
      id: 'user-123',
      email: 'overseer@vault.com',
      username: 'Overseer'
    }

    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profile', component: ProfileView }]
    })

    vi.clearAllMocks()
  })

  // Helper to mock both API calls
  const mockBothApis = () => {
    vi.mocked(axios.get).mockImplementation((url: string) => {
      if (url === '/api/v1/users/me/profile') {
        return Promise.resolve({ data: mockProfile })
      }
      if (url === '/api/v1/users/me/profile/statistics') {
        return Promise.resolve({ data: mockDeathStatistics })
      }
      return Promise.reject(new Error('Unknown URL'))
    })
  }

  describe('Component Mounting', () => {
    it('should render profile view', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('OVERSEER PROFILE')
    })

    it('should fetch profile on mount', async () => {
      mockBothApis()

      mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile')
    })

    it('should fetch death statistics on mount', async () => {
      mockBothApis()

      mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile/statistics')
    })
  })

  describe('Loading State', () => {
    it('should show loading indicator while fetching profile', async () => {
      vi.mocked(axios.get).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockProfile }), 100))
      )

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })

      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('Loading profile...')
    })

    it('should hide loading indicator after profile loads', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).not.toContain('Loading profile...')
    })
  })

  describe('Error State', () => {
    it('should display error message on fetch failure', async () => {
      const errorMessage = 'Failed to fetch profile'
      vi.mocked(axios.get).mockRejectedValueOnce({
        response: { data: { detail: errorMessage } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('ERROR: PROFILE LOAD FAILURE')
      expect(wrapper.text()).toContain(errorMessage)
    })

    it('should show retry button on error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce({
        response: { data: { detail: 'Network error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Retry Connection')
    })

    it('should retry fetching profile when retry button is clicked', async () => {
      vi.mocked(axios.get)
        .mockRejectedValueOnce({ response: { data: { detail: 'Network error' } } })
        .mockImplementation((url: string) => {
          if (url === '/api/v1/users/me/profile') {
            return Promise.resolve({ data: mockProfile })
          }
          if (url === '/api/v1/users/me/profile/statistics') {
            return Promise.resolve({ data: mockDeathStatistics })
          }
          return Promise.reject(new Error('Unknown URL'))
        })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const retryButton = wrapper.findAll('button').find((btn) => btn.text().includes('Retry'))
      await retryButton?.trigger('click')
      await flushPromises()

      // Initial fail (1) + statistics attempt (2) + retry profile (3) + retry statistics (4)
      expect(axios.get).toHaveBeenCalledTimes(4)
      expect(wrapper.text()).not.toContain('ERROR: PROFILE LOAD FAILURE')
    })
  })

  describe('Profile Display', () => {
    beforeEach(() => {
      mockBothApis()
    })

    it('should display user email from auth store', async () => {
      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('overseer@vault.com')
    })

    it('should display bio when provided', async () => {
      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Test bio for overseer')
    })

    it('should display avatar when URL is provided', async () => {
      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const avatar = wrapper.find('img[alt="Profile avatar"]')
      expect(avatar.exists()).toBe(true)
      expect(avatar.attributes('src')).toBe('https://example.com/avatar.jpg')
    })

    it('should display preferences as JSON', async () => {
      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const prefsText = wrapper.text()
      expect(prefsText).toContain('"theme": "dark"')
      expect(prefsText).toContain('"notifications": true')
    })

    it('should display created and updated timestamps', async () => {
      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('FILE CREATED:')
      expect(wrapper.text()).toContain('LAST MODIFIED:')
    })
  })

  describe('LifeDeathStatistics Component', () => {
    it('should render LifeDeathStatistics component', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const statsComponent = wrapper.findComponent(LifeDeathStatistics)
      expect(statsComponent.exists()).toBe(true)
    })

    it('should pass death statistics to LifeDeathStatistics component', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const statsComponent = wrapper.findComponent(LifeDeathStatistics)
      expect(statsComponent.props('statistics')).toEqual(mockDeathStatistics)
    })

    it('should pass loading state to LifeDeathStatistics component', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const statsComponent = wrapper.findComponent(LifeDeathStatistics)
      expect(statsComponent.props('loading')).toBe(false)
    })
  })

  describe('Edit Mode', () => {
    it('should show edit button in display mode', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.findAll('button').find((btn) => btn.text().includes('Edit'))
      expect(editButton?.exists()).toBe(true)
    })

    it('should switch to edit mode when edit button is clicked', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.findAll('button').find((btn) => btn.text().includes('Edit'))
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      expect(editorComponent.exists()).toBe(true)
    })

    it('should hide display mode when in edit mode', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.findAll('button').find((btn) => btn.text().includes('Edit'))
      await editButton?.trigger('click')
      await flushPromises()

      // Personnel File card should not be visible in edit mode
      expect(wrapper.text()).not.toContain('PERSONNEL FILE')
    })
  })

  describe('ProfileEditor Integration', () => {
    const findEditButton = (wrapper: any) =>
      wrapper.findAll('button').find((btn: any) => btn.text().includes('Edit'))

    it('should render ProfileEditor with initial data', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      expect(editorComponent.props('initialData')).toEqual(mockProfile)
    })

    it('should submit profile update when editor emits submit', async () => {
      mockBothApis()
      const updatedProfile = { ...mockProfile, bio: 'Updated bio' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: updatedProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Updated bio' })
      await flushPromises()

      expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', { bio: 'Updated bio' })
    })

    it('should exit edit mode after successful update', async () => {
      mockBothApis()
      const updatedProfile = { ...mockProfile, bio: 'Updated bio' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: updatedProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Updated bio' })
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
    })

    it('should cancel edit mode when editor emits cancel', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('cancel')
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
    })

    it('should stay in edit mode if update fails', async () => {
      mockBothApis()
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Validation error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Invalid data' })
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(true)
    })

    it('should pass loading state to editor', async () => {
      mockBothApis()
      vi.mocked(axios.put).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockProfile }), 100))
      )

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'New bio' })
      await wrapper.vm.$nextTick()

      expect(editorComponent.props('loading')).toBe(true)
    })

    it('should pass error state to editor', async () => {
      mockBothApis()
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Validation error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Invalid' })
      await flushPromises()

      expect(editorComponent.props('error')).toBe('Validation error')
    })
  })

  describe('Error Clearing', () => {
    const findEditButton = (wrapper: any) =>
      wrapper.findAll('button').find((btn: any) => btn.text().includes('Edit'))

    it('should clear error when entering edit mode', async () => {
      mockBothApis()

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      // Manually set an error to simulate a previous error state
      profileStore.error = 'Some previous error'

      // Enter edit mode - should clear error
      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      expect(profileStore.error).toBeNull()
    })

    it('should clear error when canceling edit mode', async () => {
      mockBothApis()
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Update error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = findEditButton(wrapper)
      await editButton?.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Test' })
      await flushPromises()

      editorComponent.vm.$emit('cancel')
      await flushPromises()

      expect(profileStore.error).toBeNull()
    })
  })
})
