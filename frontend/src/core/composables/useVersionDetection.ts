import { ref, computed, watch, readonly } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'

interface VersionInfo {
  current: string
  lastSeen: string | null
  hasUpdate: boolean
  isFirstTime: boolean
}

const STORAGE_KEY = 'fallout_changelog_last_seen'

export function useVersionDetection() {
  const authStore = useAuthStore()

  // Get current version from package.json (injected at build time)
  const currentVersion = ref(__APP_VERSION__ || '2.7.0')
  const lastSeenVersion = ref<string | null>(localStorage.getItem(STORAGE_KEY))
  const showChangelogModal = ref(false)
  const isLoading = ref(false)
  const error = ref('')

  // Computed properties
  const versionInfo = computed<VersionInfo>(() => ({
    current: currentVersion.value,
    lastSeen: lastSeenVersion.value,
    hasUpdate: hasVersionUpdate.value,
    isFirstTime: !lastSeenVersion.value,
  }))

  const hasVersionUpdate = computed(() => {
    if (!lastSeenVersion.value) return true

    // Simple version comparison
    const [lastMajor, lastMinor, lastPatch] = lastSeenVersion.value.split('.').map(Number)
    const [currMajor, currMinor, currPatch] = currentVersion.value.split('.').map(Number)

    if (currMajor > lastMajor) return true
    if (currMajor === lastMajor && currMinor > lastMinor) return true
    if (currMajor === lastMajor && currMinor === lastMinor && currPatch > lastPatch) return true

    return false
  })

  // Create a computed property for the version badge
  const versionBadgeVisible = computed(() => {
    return hasVersionUpdate.value && !showChangelogModal.value
  })

  // Actions
  const markVersionAsSeen = (version: string) => {
    localStorage.setItem(STORAGE_KEY, version)
    lastSeenVersion.value = version
    showChangelogModal.value = false
  }

  const showChangelog = () => {
    showChangelogModal.value = true
  }

  const hideChangelog = () => {
    showChangelogModal.value = false
  }

  const resetVersionTracking = () => {
    localStorage.removeItem(STORAGE_KEY)
    lastSeenVersion.value = null
  }

  // Auto-show changelog when version changes
  watch(
    [currentVersion, () => authStore.isAuthenticated],
    async ([newVersion, isAuthenticated]) => {
      // Only show changelog for authenticated users when we have a version
      if (isAuthenticated && newVersion && hasVersionUpdate.value) {
        // Small delay to ensure app is fully loaded
        setTimeout(() => {
          showChangelogModal.value = true
        }, 1000)
      }
    },
    { immediate: true }
  )

  return {
    // State
    currentVersion: readonly(currentVersion),
    lastSeenVersion: readonly(lastSeenVersion),
    showChangelogModal: readonly(showChangelogModal),
    isLoading: readonly(isLoading),
    error: readonly(error),

    // Computed
    versionInfo: readonly(versionInfo),
    hasVersionUpdate: readonly(hasVersionUpdate),
    versionBadgeVisible: readonly(versionBadgeVisible),

    // Actions
    markVersionAsSeen,
    showChangelog,
    hideChangelog,
    resetVersionTracking,
  }
}
