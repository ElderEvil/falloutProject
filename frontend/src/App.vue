<script setup lang="ts">
import { provide } from 'vue'
import DefaultLayout from '@/modules/vault/components/shell/DefaultLayout.vue'
import UToastContainer from '@/core/components/ui/UToastContainer.vue'
import ChangelogModal from '@/modules/profile/components/ChangelogModal.vue'
import GaryOverlay from '@/core/components/easter-eggs/GaryOverlay.vue'
import FakeCrashOverlay from '@/core/components/easter-eggs/FakeCrashOverlay.vue'
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { useTheme } from '@/core/composables/useTheme'
import { useTokenRefresh } from '@/core/composables/useTokenRefresh'
import { useResourceWarnings } from '@/modules/vault/composables/useResourceWarnings'
import { useVersionDetection } from '@/core/composables/useVersionDetection'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { useFakeCrash } from '@/core/composables/useFakeCrash'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Visual effects (replaces old useFlickering)
const visualEffects = useVisualEffects()
const { flickering, scanlines, glowClass, flickerOpacity } = visualEffects

// Theme system
const { currentTheme, setTheme, availableThemes } = useTheme()

// Token refresh system (auto-refreshes tokens before expiry)
const authStore = useAuthStore()
useTokenRefresh({
  getToken: () => authStore.token,
  getRefreshToken: () => authStore.refreshToken,
  isAuthenticated: () => authStore.isAuthenticated,
  refreshAccessToken: () => authStore.refreshAccessToken(),
  logout: () => authStore.logout(),
})

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
    <UToastContainer />

    <!-- Changelog Modal -->
    <ChangelogModal
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
