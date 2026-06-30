import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

vi.stubGlobal('__APP_VERSION__', '2.18.0')

const mockAuthStore = {
  isAuthenticated: false,
}
vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

import { useVersionDetection } from '@/core/composables/useVersionDetection'

const STORAGE_KEY = 'fallout_changelog_last_seen'

describe('useVersionDetection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockAuthStore.isAuthenticated = false
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('should detect first time visit when no stored version', () => {
    const { versionInfo, hasVersionUpdate } = useVersionDetection()

    expect(versionInfo.value.isFirstTime).toBe(true)
    expect(hasVersionUpdate.value).toBe(true)
    expect(versionInfo.value.current).toBe('2.18.0')
    expect(versionInfo.value.lastSeen).toBeNull()
  })

  it('should detect version update when current > lastSeen', () => {
    localStorage.setItem(STORAGE_KEY, '2.17.0')

    const { hasVersionUpdate } = useVersionDetection()

    expect(hasVersionUpdate.value).toBe(true)
  })

  it('should not detect update when versions match', () => {
    localStorage.setItem(STORAGE_KEY, '2.18.0')

    const { hasVersionUpdate } = useVersionDetection()

    expect(hasVersionUpdate.value).toBe(false)
  })

  it('should not detect update when lastSeen > current', () => {
    localStorage.setItem(STORAGE_KEY, '3.0.0')

    const { hasVersionUpdate } = useVersionDetection()

    expect(hasVersionUpdate.value).toBe(false)
  })

  it('should detect update on major version bump', () => {
    localStorage.setItem(STORAGE_KEY, '1.9.9')

    const { hasVersionUpdate } = useVersionDetection()

    expect(hasVersionUpdate.value).toBe(true)
  })

  it('should detect update on patch version bump', () => {
    localStorage.setItem(STORAGE_KEY, '2.18.0')

    const { hasVersionUpdate } = useVersionDetection()

    expect(hasVersionUpdate.value).toBe(false)
  })

  it('markVersionAsSeen stores version and hides changelog', () => {
    const { markVersionAsSeen, showChangelogModal, hasVersionUpdate } = useVersionDetection()

    markVersionAsSeen('2.18.0')

    expect(localStorage.getItem(STORAGE_KEY)).toBe('2.18.0')
    expect(showChangelogModal.value).toBe(false)
    expect(hasVersionUpdate.value).toBe(false)
  })

  it('versionBadgeVisible is true when update exists and modal hidden', () => {
    const { versionBadgeVisible, showChangelog } = useVersionDetection()

    expect(versionBadgeVisible.value).toBe(true)

    showChangelog()
    expect(versionBadgeVisible.value).toBe(false)
  })

  it('showChangelog and hideChangelog toggle modal', () => {
    const { showChangelogModal, showChangelog, hideChangelog } = useVersionDetection()

    expect(showChangelogModal.value).toBe(false)

    showChangelog()
    expect(showChangelogModal.value).toBe(true)

    hideChangelog()
    expect(showChangelogModal.value).toBe(false)
  })

  it('resetVersionTracking clears stored version', () => {
    localStorage.setItem(STORAGE_KEY, '2.18.0')

    const { resetVersionTracking, lastSeenVersion, hasVersionUpdate } = useVersionDetection()

    resetVersionTracking()

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(lastSeenVersion.value).toBeNull()
    expect(hasVersionUpdate.value).toBe(true)
  })

  it('versionInfo returns complete version info object', () => {
    localStorage.setItem(STORAGE_KEY, '2.17.0')

    const { versionInfo } = useVersionDetection()

    expect(versionInfo.value).toEqual({
      current: '2.18.0',
      lastSeen: '2.17.0',
      hasUpdate: true,
      isFirstTime: false,
    })
  })

  it('versionBadgeVisible is false when modal is shown', () => {
    const { versionBadgeVisible, showChangelog } = useVersionDetection()

    showChangelog()

    expect(versionBadgeVisible.value).toBe(false)
  })
})
