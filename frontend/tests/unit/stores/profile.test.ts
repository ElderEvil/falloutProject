import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProfileStore } from '@/stores/profile'
import axios from '@/core/plugins/axios'
import type { UserProfile, ProfileUpdate } from '@/models/profile'

vi.mock('@/core/plugins/axios')

describe('Profile Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

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
    updated_at: '2023-01-02T00:00:00Z'
  }

  describe('State Initialization', () => {
    it('should initialize with null profile', () => {
      const store = useProfileStore()
      expect(store.profile).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('Getters', () => {
    it('hasProfile should return true when profile exists', () => {
      const store = useProfileStore()
      store.profile = mockProfile
      expect(store.hasProfile).toBe(true)
    })

    it('hasProfile should return false when profile is null', () => {
      const store = useProfileStore()
      expect(store.hasProfile).toBe(false)
    })

    it('statistics should return formatted statistics when profile exists', () => {
      const store = useProfileStore()
      store.profile = mockProfile

      expect(store.statistics).toEqual({
        totalDwellersCreated: 10,
        totalCapsEarned: 500,
        totalExplorations: 5,
        totalRoomsBuilt: 8
      })
    })

    it('statistics should return null when profile is null', () => {
      const store = useProfileStore()
      expect(store.statistics).toBeNull()
    })
  })

  describe('fetchProfile Action', () => {
    it('should fetch profile successfully', async () => {
      const store = useProfileStore()
      const mockResponse = { data: mockProfile }

      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse)

      await store.fetchProfile()

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me/profile')
      expect(store.profile).toEqual(mockProfile)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set loading state during fetch', async () => {
      const store = useProfileStore()
      const mockResponse = { data: mockProfile }

      vi.mocked(axios.get).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve(mockResponse)
      })

      await store.fetchProfile()
      expect(store.loading).toBe(false)
    })

    it('should handle fetch error with detail message', async () => {
      const store = useProfileStore()
      const mockError = {
        response: {
          data: {
            detail: 'Profile not found'
          }
        }
      }

      vi.mocked(axios.get).mockRejectedValueOnce(mockError)

      await expect(store.fetchProfile()).rejects.toEqual(mockError)
      expect(store.error).toBe('Profile not found')
      expect(store.profile).toBeNull()
      expect(store.loading).toBe(false)
    })

    it('should handle fetch error with generic message', async () => {
      const store = useProfileStore()
      const mockError = new Error('Network error')

      vi.mocked(axios.get).mockRejectedValueOnce(mockError)

      await expect(store.fetchProfile()).rejects.toEqual(mockError)
      expect(store.error).toBe('Failed to fetch profile')
      expect(store.loading).toBe(false)
    })
  })

  describe('updateProfile Action', () => {
    const updateData: ProfileUpdate = {
      bio: 'Updated bio',
      avatar_url: 'https://example.com/new-avatar.jpg',
      preferences: { theme: 'light', notifications: true }
    }

    it('should update profile successfully', async () => {
      const store = useProfileStore()
      const updatedProfile = { ...mockProfile, ...updateData }
      const mockResponse = { data: updatedProfile }

      vi.mocked(axios.put).mockResolvedValueOnce(mockResponse)

      await store.updateProfile(updateData)

      expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', updateData)
      expect(store.profile).toEqual(updatedProfile)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set loading state during update', async () => {
      const store = useProfileStore()
      const mockResponse = { data: mockProfile }

      vi.mocked(axios.put).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve(mockResponse)
      })

      await store.updateProfile(updateData)
      expect(store.loading).toBe(false)
    })

    it('should handle update error with detail message', async () => {
      const store = useProfileStore()
      const mockError = {
        response: {
          data: {
            detail: 'Validation error'
          }
        }
      }

      vi.mocked(axios.put).mockRejectedValueOnce(mockError)

      await expect(store.updateProfile(updateData)).rejects.toEqual(mockError)
      expect(store.error).toBe('Validation error')
      expect(store.loading).toBe(false)
    })

    it('should handle update error with generic message', async () => {
      const store = useProfileStore()
      const mockError = new Error('Network error')

      vi.mocked(axios.put).mockRejectedValueOnce(mockError)

      await expect(store.updateProfile(updateData)).rejects.toEqual(mockError)
      expect(store.error).toBe('Failed to update profile')
      expect(store.loading).toBe(false)
    })

    it('should update profile with partial data', async () => {
      const store = useProfileStore()
      const partialUpdate: ProfileUpdate = { bio: 'New bio only' }
      const updatedProfile = { ...mockProfile, bio: 'New bio only' }
      const mockResponse = { data: updatedProfile }

      vi.mocked(axios.put).mockResolvedValueOnce(mockResponse)

      await store.updateProfile(partialUpdate)

      expect(axios.put).toHaveBeenCalledWith('/api/v1/users/me/profile', partialUpdate)
      expect(store.profile?.bio).toBe('New bio only')
    })

    it('should update profile with null values', async () => {
      const store = useProfileStore()
      const nullUpdate: ProfileUpdate = { bio: null, avatar_url: null }
      const updatedProfile = { ...mockProfile, bio: null, avatar_url: null }
      const mockResponse = { data: updatedProfile }

      vi.mocked(axios.put).mockResolvedValueOnce(mockResponse)

      await store.updateProfile(nullUpdate)

      expect(store.profile?.bio).toBeNull()
      expect(store.profile?.avatar_url).toBeNull()
    })
  })

  describe('clearError Action', () => {
    it('should clear error state', () => {
      const store = useProfileStore()
      store.error = 'Some error'

      store.clearError()

      expect(store.error).toBeNull()
    })
  })
})
