import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createApiClientMock } from '../helpers/mocks'
import { setActivePinia, createPinia } from 'pinia'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { apiGet, apiPut } from '@/core/utils/api'
import type { UserProfile, ProfileUpdate } from '@/models/profile'

vi.mock('@/core/utils/api', () => createApiClientMock())

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

const mockDeathStats = {
  total_dwellers_born: 50,
  total_dwellers_died: 10,
  deaths_by_cause: { health: 3, radiation: 2, incident: 2, exploration: 2, combat: 1 },
  revivable_count: 3,
  permanently_dead_count: 7,
}

/** The API's structured failure shape. */
const apiError = (detail: string) => ({ response: { data: { detail } } })

const profileWith = (overrides: Partial<UserProfile>) => ({ ...mockProfile, ...overrides })

function deferred<T = unknown>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('Profile Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('State Initialization', () => {
    it('should initialize with null profile', () => {
      const store = useProfileStore()
      expect(store.profile).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('Getters', () => {
    it('hasProfile follows the profile', () => {
      const store = useProfileStore()
      expect(store.hasProfile).toBe(false)
      store.profile = mockProfile
      expect(store.hasProfile).toBe(true)
    })

    it('statistics should return formatted statistics when profile exists', () => {
      const store = useProfileStore()
      expect(store.statistics).toBeNull()

      store.profile = mockProfile
      expect(store.statistics).toEqual({
        totalDwellersCreated: 10,
        totalCapsEarned: 500,
        totalExplorations: 5,
        totalRoomsBuilt: 8,
      })
    })
  })

  describe('fetchProfile Action', () => {
    it('should fetch profile successfully and flag loading while in flight', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve(mockProfile)
      })

      await store.fetchProfile()
      expect(apiGet).toHaveBeenCalledWith('/api/v1/users/me/profile')
      expect(store.profile).toEqual(mockProfile)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it.each([
      ['a structured detail message', apiError('Profile not found'), 'Profile not found'],
      ['a plain error message', new Error('Network error'), 'Network error'],
    ])('should handle fetch error with %s', async (_, mockError, message) => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockRejectedValueOnce(mockError)

      await expect(store.fetchProfile()).rejects.toEqual(mockError)
      expect(store.error).toBe(message)
      expect(store.profile).toBeNull()
      expect(store.loading).toBe(false)
    })
  })

  describe('refreshProfile Action', () => {
    it('refreshes the record without entering the page-loading state', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockImplementation(() => {
        expect(store.profileRefreshing).toBe(true)
        expect(store.loading).toBe(false)
        return Promise.resolve(mockProfile)
      })

      await store.refreshProfile()
      expect(store.profile).toEqual(mockProfile)
      expect(store.profileRefreshing).toBe(false)
    })

    it('does not overwrite a saved profile with an older refresh response', async () => {
      const store = useProfileStore()
      const refresh = deferred<UserProfile>()
      vi.mocked(apiGet).mockReturnValueOnce(refresh.promise)

      const pending = store.refreshProfile()
      const savedProfile = profileWith({ bio: 'Saved bio' })
      vi.mocked(apiPut).mockResolvedValueOnce(savedProfile)
      await store.updateProfile({ bio: savedProfile.bio })
      refresh.resolve(mockProfile)
      await pending
      expect(store.profile).toEqual(savedProfile)
    })
  })

  describe('updateProfile Action', () => {
    const updateData: ProfileUpdate = {
      bio: 'Updated bio',
      avatar_url: 'https://example.com/new-avatar.jpg',
      preferences: { theme: 'light', notifications: true },
    }

    it('should update profile successfully and flag loading while in flight', async () => {
      const store = useProfileStore()
      const updatedProfile = { ...mockProfile, ...updateData }
      vi.mocked(apiPut).mockImplementation(() => {
        expect(store.loading).toBe(true)
        return Promise.resolve(updatedProfile)
      })

      await store.updateProfile(updateData)
      expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', updateData)
      expect(store.profile).toEqual(updatedProfile)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it.each([
      ['a structured detail message', apiError('Validation error'), 'Validation error'],
      ['a plain error message', new Error('Network error'), 'Network error'],
    ])('should handle update error with %s', async (_, mockError, message) => {
      const store = useProfileStore()
      vi.mocked(apiPut).mockRejectedValueOnce(mockError)

      await expect(store.updateProfile(updateData)).rejects.toEqual(mockError)
      expect(store.error).toBe(message)
      expect(store.loading).toBe(false)
    })

    it('should apply partial updates and explicit nulls', async () => {
      const store = useProfileStore()
      const partialUpdate: ProfileUpdate = { bio: 'New bio only' }
      vi.mocked(apiPut).mockResolvedValueOnce(profileWith({ bio: 'New bio only' }))

      await store.updateProfile(partialUpdate)
      expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', partialUpdate)
      expect(store.profile?.bio).toBe('New bio only')

      const nullUpdate: ProfileUpdate = { bio: null, avatar_url: null }
      vi.mocked(apiPut).mockResolvedValueOnce(profileWith(nullUpdate))
      await store.updateProfile(nullUpdate)
      expect(store.profile?.bio).toBeNull()
      expect(store.profile?.avatar_url).toBeNull()
    })
  })

  describe('ensureProfileLoaded Action', () => {
    it('fetches the profile when empty', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockResolvedValueOnce(mockProfile)
      await store.ensureProfileLoaded()
      expect(apiGet).toHaveBeenCalledWith('/api/v1/users/me/profile')
      expect(store.profile).toEqual(mockProfile)
    })

    it('skips the fetch when profile is already set', async () => {
      const store = useProfileStore()
      store.profile = mockProfile
      await store.ensureProfileLoaded()
      expect(apiGet).not.toHaveBeenCalled()
    })

    it('skips the fetch while loading is true', async () => {
      const store = useProfileStore()
      store.loading = true
      await store.ensureProfileLoaded()
      expect(apiGet).not.toHaveBeenCalled()
    })

    it('swallows fetch errors', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockRejectedValueOnce(new Error('Network error'))
      await expect(store.ensureProfileLoaded()).resolves.toBeUndefined()
      expect(store.error).toBe('Network error')
      expect(store.profile).toBeNull()
      expect(store.loading).toBe(false)
    })
  })

  describe('clearProfile Action', () => {
    it('resets profile, death statistics, AI usage stats and error to null', () => {
      const store = useProfileStore()
      store.profile = mockProfile
      store.deathStatistics = mockDeathStats
      store.aiUsageStats = {
        all_time: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        current_month: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        month: '2026-09',
        quota_limit: 100,
        quota_used: 10,
        quota_remaining: 90,
        quota_percentage: 10,
        quota_warning: false,
        quota_exceeded: false,
        reset_date: '2026-10-01',
      }
      store.error = 'Some error'

      store.clearProfile()
      expect(store.profile).toBeNull()
      expect(store.deathStatistics).toBeNull()
      expect(store.aiUsageStats).toBeNull()
      expect(store.error).toBeNull()
    })
  })

  it.each(['resolve', 'reject'] as const)(
    'isolates a new profile load when the previous session request will %s',
    async (outcome) => {
      const store = useProfileStore()
      const oldResponse = deferred<UserProfile>()
      const newResponse = deferred<UserProfile>()
      vi.mocked(apiGet)
        .mockReturnValueOnce(oldResponse.promise)
        .mockReturnValueOnce(newResponse.promise)
      const oldLoad = store.ensureProfileLoaded()
      store.clearProfile()
      const newLoad = store.ensureProfileLoaded()
      expect(apiGet).toHaveBeenCalledTimes(2)

      if (outcome === 'resolve') oldResponse.resolve(mockProfile)
      else oldResponse.reject(new Error('Old session expired'))
      await oldLoad
      expect(store.profile).toBeNull()
      expect(store.error).toBeNull()
      expect(store.loading).toBe(true)

      const nextProfile = profileWith({ user_id: 'new-user', avatar_url: '/new.png' })
      newResponse.resolve(nextProfile)
      await newLoad
      expect(store.profile).toEqual(nextProfile)
      expect(store.loading).toBe(false)
    }
  )

  describe('savePreferences Action', () => {
    it('persists notification category opt-outs in the versioned preference key', async () => {
      const store = useProfileStore()
      store.profile = mockProfile
      const updatedProfile = profileWith({
        preferences: {
          theme: 'dark',
          notifications: { version: 1, disabled_categories: ['advancement'] },
        },
      })
      vi.mocked(apiPut).mockResolvedValueOnce(updatedProfile)

      await store.savePreferences({
        notifications: { version: 1, disabled_categories: ['advancement'] },
      })
      expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', {
        preferences: updatedProfile.preferences,
      })
      expect(store.profile).toEqual(updatedProfile)
    })

    it('merges the patch into the latest confirmed preferences', async () => {
      const store = useProfileStore()
      store.profile = profileWith({ preferences: { theme: 'fnv', sound: { muted: true } } })
      const updatedProfile = profileWith({
        preferences: { theme: 'fnv', sound: { muted: false } },
      })
      vi.mocked(apiPut).mockResolvedValueOnce(updatedProfile)

      await store.savePreferences({ sound: { muted: false } })
      expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', {
        preferences: { theme: 'fnv', sound: { muted: false } },
      })
      expect(store.profile).toEqual(updatedProfile)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('serializes overlapping saves and merges each with the latest preferences', async () => {
      const store = useProfileStore()
      store.profile = profileWith({ preferences: { theme: 'fnv' } })
      const firstSave = deferred<UserProfile>()
      vi.mocked(apiPut)
        .mockReturnValueOnce(firstSave.promise)
        .mockResolvedValueOnce(
          profileWith({ preferences: { theme: 'fnv', sound: { muted: false } } })
        )

      const first = store.savePreferences({ theme: 'fnv' })
      const second = store.savePreferences({ sound: { muted: false } })
      await Promise.resolve()
      expect(apiPut).toHaveBeenCalledTimes(1)
      firstSave.resolve(profileWith({ preferences: { theme: 'fnv' } }))
      await first
      await second
      expect(apiPut).toHaveBeenCalledTimes(2)
      expect(apiPut).toHaveBeenLastCalledWith('/api/v1/users/me/profile', {
        preferences: { theme: 'fnv', sound: { muted: false } },
      })
    })

    it('ignores a save response that arrives after the profile is cleared', async () => {
      const store = useProfileStore()
      store.profile = mockProfile
      const save = deferred<UserProfile>()
      vi.mocked(apiPut).mockReturnValueOnce(save.promise)

      const pending = store.savePreferences({ theme: 'light' })
      store.clearProfile()
      save.resolve(profileWith({ preferences: { theme: 'light' } }))
      await pending
      expect(store.profile).toBeNull()
    })

    it('throws on failure without setting error or loading', async () => {
      const store = useProfileStore()
      const mockError = new Error('Network error')
      vi.mocked(apiPut).mockRejectedValueOnce(mockError)
      await expect(store.savePreferences({ theme: 'light' })).rejects.toEqual(mockError)
      expect(store.error).toBeNull()
      expect(store.loading).toBe(false)
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

  describe('Death Statistics', () => {
    it('should initialize with null death statistics', () => {
      const store = useProfileStore()
      expect(store.deathStatistics).toBeNull()
      expect(store.deathStatsLoading).toBe(false)
    })

    it('should fetch death statistics successfully', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockResolvedValueOnce(mockDeathStats)

      const result = await store.fetchDeathStatistics()
      expect(apiGet).toHaveBeenCalledWith('/api/v1/users/me/profile/statistics')
      expect(store.deathStatistics).toEqual(mockDeathStats)
      expect(result).toEqual(mockDeathStats)
      expect(store.deathStatsLoading).toBe(false)
    })

    it('should set loading state during fetch', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockImplementation(() => {
        expect(store.deathStatsLoading).toBe(true)
        return Promise.resolve(mockDeathStats)
      })

      await store.fetchDeathStatistics()
      expect(store.deathStatsLoading).toBe(false)
    })

    it('should handle fetch error and return null', async () => {
      const store = useProfileStore()
      vi.mocked(apiGet).mockRejectedValueOnce(new Error('Network error'))
      expect(await store.fetchDeathStatistics()).toBeNull()
      expect(store.deathStatsLoading).toBe(false)
    })
  })
})
