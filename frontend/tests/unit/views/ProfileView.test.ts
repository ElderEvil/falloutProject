import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProfileView from '@/modules/profile/views/ProfileView.vue'
import ProfileEditor from '@/modules/profile/components/ProfileEditor.vue'
import ProfileStats from '@/modules/profile/components/ProfileStats.vue'
import { useProfileStore } from '@/stores/profile'
import { useAuthStore } from '@/stores/auth'
import axios from '@/core/plugins/axios'
import type { UserProfile } from '@/models/profile'

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

  describe('Component Mounting', () => {
    it('should render profile view', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Overseer Profile')
    })

    it('should fetch profile on mount', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile')
    })
  })

  describe('Loading State', () => {
    it('should show loading indicator while fetching profile', async () => {
      vi.mocked(axios.get).mockImplementationOnce(
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
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

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

      expect(wrapper.text()).toContain('Error Loading Profile')
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

      const retryButton = wrapper.find('button')
      expect(retryButton.exists()).toBe(true)
      expect(retryButton.text()).toContain('Retry')
    })

    it('should retry fetching profile when retry button is clicked', async () => {
      vi.mocked(axios.get)
        .mockRejectedValueOnce({ response: { data: { detail: 'Network error' } } })
        .mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const retryButton = wrapper.find('button')
      await retryButton.trigger('click')
      await flushPromises()

      expect(axios.get).toHaveBeenCalledTimes(2)
      expect(wrapper.text()).not.toContain('Error Loading Profile')
    })
  })

  describe('Profile Display', () => {
    beforeEach(async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
    })

    it('should display user email from auth store', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('overseer@vault.com')
    })

    it('should display bio when provided', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Test bio for overseer')
    })

    it('should display avatar when URL is provided', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

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
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

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
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Created:')
      expect(wrapper.text()).toContain('Updated:')
    })
  })

  describe('ProfileStats Component', () => {
    it('should render ProfileStats component', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const statsComponent = wrapper.findComponent(ProfileStats)
      expect(statsComponent.exists()).toBe(true)
    })

    it('should pass statistics to ProfileStats component', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const statsComponent = wrapper.findComponent(ProfileStats)
      expect(statsComponent.props('statistics')).toEqual({
        totalDwellersCreated: 10,
        totalCapsEarned: 5000,
        totalExplorations: 25,
        totalRoomsBuilt: 8
      })
    })
  })

  describe('Edit Mode', () => {
    it('should show edit button in display mode', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      expect(editButton.text()).toContain('Edit Profile')
    })

    it('should switch to edit mode when edit button is clicked', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      expect(editorComponent.exists()).toBe(true)
    })

    it('should hide display mode when in edit mode', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      // Check that Personal Information section is not visible (only editor is shown)
      const personalInfoSection = wrapper.find('.bg-gray-800 h2')
      expect(personalInfoSection.text()).not.toBe('Personal Information')
    })
  })

  describe('ProfileEditor Integration', () => {
    it('should render ProfileEditor with initial data', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      expect(editorComponent.props('initialData')).toEqual(mockProfile)
    })

    it('should submit profile update when editor emits submit', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      const updatedProfile = { ...mockProfile, bio: 'Updated bio' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: updatedProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Updated bio' })
      await flushPromises()

      expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', { bio: 'Updated bio' })
    })

    it('should exit edit mode after successful update', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      const updatedProfile = { ...mockProfile, bio: 'Updated bio' }
      vi.mocked(axios.put).mockResolvedValueOnce({ data: updatedProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Updated bio' })
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
      expect(wrapper.text()).toContain('Edit Profile')
    })

    it('should cancel edit mode when editor emits cancel', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('cancel')
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(false)
      expect(wrapper.text()).toContain('Edit Profile')
    })

    it('should stay in edit mode if update fails', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Validation error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Invalid data' })
      await flushPromises()

      expect(wrapper.findComponent(ProfileEditor).exists()).toBe(true)
    })

    it('should pass loading state to editor', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      vi.mocked(axios.put).mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ data: mockProfile }), 100))
      )

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'New bio' })
      await wrapper.vm.$nextTick()

      expect(editorComponent.props('loading')).toBe(true)
    })

    it('should pass error state to editor', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Validation error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      const editorComponent = wrapper.findComponent(ProfileEditor)
      editorComponent.vm.$emit('submit', { bio: 'Invalid' })
      await flushPromises()

      expect(editorComponent.props('error')).toBe('Validation error')
    })
  })

  describe('Error Clearing', () => {
    it('should clear error when entering edit mode', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce({
        response: { data: { detail: 'Error' } }
      })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const retryButton = wrapper.find('button')
      await retryButton.trigger('click')
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
      await flushPromises()

      expect(profileStore.error).toBeNull()
    })

    it('should clear error when canceling edit mode', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockProfile })
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Update error' } }
      })

      const wrapper = mount(ProfileView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const editButton = wrapper.find('button')
      await editButton.trigger('click')
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
