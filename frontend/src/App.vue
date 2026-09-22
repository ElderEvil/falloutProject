<script setup lang="ts">
import { defineAsyncComponent, provide, watch } from 'vue'
import DefaultLayout from '@/modules/vault/components/shell/DefaultLayout.vue'
import { Toaster } from '@/core/components/ui/toast'
import GaryOverlay from '@/core/components/easter-eggs/GaryOverlay.vue'
import FakeCrashOverlay from '@/core/components/easter-eggs/FakeCrashOverlay.vue'
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { useTheme } from '@/core/composables/useTheme'
import { useBadgeStyle } from '@/core/composables/useBadgeStyle'
import { useTokenRefresh } from '@/core/composables/useTokenRefresh'
import { useResourceWarnings } from '@/modules/vault/composables/useResourceWarnings'
import { useVersionDetection } from '@/core/composables/useVersionDetection'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { useFakeCrash } from '@/core/composables/useFakeCrash'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useSoundProfileSync } from '@/modules/profile/composables/useSoundProfileSync'

// Kept out of the initial payload: the changelog only ever appears when a new
// version is detected, so its chunk must not be preloaded on every boot.
const ChangelogModal = defineAsyncComponent(() => import('@/modules/profile/components/ChangelogModal.vue'))

// Visual effects (replaces old useFlickering)
const visualEffects = useVisualEffects()
const { flickering, scanlines, glowClass, flickerOpacity } = visualEffects

// Theme system
const { currentTheme, setTheme, availableThemes } = useTheme()

// Badge palette preference (colour or monochrome); applied at boot so badges
// never flash the wrong palette before the preference loads.
useBadgeStyle()

// Token refresh system (auto-refreshes tokens before expiry)
const authStore = useAuthStore()
useTokenRefresh({
  getToken: () => authStore.token,
  getRefreshToken: () => authStore.refreshToken,
  isAuthenticated: () => authStore.isAuthenticated,
  refreshAccessToken: () => authStore.refreshAccessToken(),
  logout: () => authStore.logout(),
})

// Profile boot-loading: load once on login/reload, clear on logout.
const profileStore = useProfileStore()
watch(
  () => authStore.isAuthenticated,
  (authed) => {
    if (authed) void profileStore.ensureProfileLoaded()
    else profileStore.clearProfile()
  },
  { immediate: true }
)

// Sound settings sync: hydrate from the profile and persist local changes.
useSoundProfileSync()

// Resource warnings system
useResourceWarnings()

// Version detection and changelog system
const { showChangelogModal, versionInfo, markVersionAsSeen, hideChangelog } = useVersionDetection({
  isAuthenticated: () => authStore.isAuthenticated,
})

// Easter eggs
const { isGaryMode } = useGaryMode()
const { isCrashing, resetCrash } = useFakeCrash()

// Provide visual effects for components that need them
provide('visualEffects', visualEffects)
provide('scanlines', scanlines)
provide('glowClass', glowClass)

// Legacy support for old useFlickering consumers
provide('isFlickering', flickering)
provide('toggleFlickering', visualEffects.toggleFlickering)

// Theme providers
provide('currentTheme', currentTheme)
provide('setTheme', setTheme)
provide('availableThemes', availableThemes)
</script>

<template>
  <div>
    <DefaultLayout :isFlickering="flickering" :flicker-opacity="flickerOpacity">
      <router-view></router-view>
    </DefaultLayout>
    <Toaster />

    <!-- Changelog Modal (lazy: only fetched once a new version is detected) -->
    <ChangelogModal
      v-if="showChangelogModal"
      :show="showChangelogModal"
      :current-version="versionInfo.current"
      :last-seen-version="versionInfo.lastSeen ?? undefined"
      @close="hideChangelog"
      @mark-as-seen="markVersionAsSeen"
    />

    <!-- Easter Egg Overlays -->
    <GaryOverlay :show="isGaryMode" />
    <FakeCrashOverlay :show="isCrashing" @complete="resetCrash" />
  </div>
</template>
