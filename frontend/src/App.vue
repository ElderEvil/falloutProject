<script setup lang="ts">
import { computed, defineAsyncComponent, provide, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DefaultLayout from '@/modules/vault/components/shell/DefaultLayout.vue'
import { Toaster } from '@/core/components/ui/toast'
import GaryOverlay from '@/core/components/easter-eggs/GaryOverlay.vue'
import FakeCrashOverlay from '@/core/components/easter-eggs/FakeCrashOverlay.vue'
import { useVisualEffects } from '@/core/composables/useVisualEffects'
import { useTheme } from '@/core/composables/useTheme'
import { useBadgeStyle } from '@/core/composables/useBadgeStyle'
import { useTokenRefresh } from '@/core/composables/useTokenRefresh'
import VaultBoyFeedback from '@/core/components/common/VaultBoyFeedback.vue'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { useVaultBoyEvents } from '@/modules/vault/composables/useVaultBoyEvents'
import { useResourceWarnings } from '@/modules/vault/composables/useResourceWarnings'
import { useVersionDetection } from '@/core/composables/useVersionDetection'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { useFakeCrash } from '@/core/composables/useFakeCrash'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useSoundProfileSync } from '@/modules/profile/composables/useSoundProfileSync'

// Kept out of the initial payload: the changelog only ever appears when a new
// version is detected, so its chunk must not be preloaded on every boot.
const ChangelogModal = defineAsyncComponent(
  () => import('@/modules/profile/components/ChangelogModal.vue')
)

// Dweller chat opens as a modal over the current view (dweller detail, map,
// roster) via `?chat=<dwellerId>`; the chunk loads only when chat is requested.
const DwellerChatModal = defineAsyncComponent(
  () => import('@/modules/chat/components/DwellerChatModal.vue')
)
const DwellerDetailModal = defineAsyncComponent(
  () => import('@/modules/dwellers/components/modals/DwellerDetailModal.vue')
)

const route = useRoute()
const router = useRouter()
const dwellerVaultId = computed(() =>
  route.path.startsWith('/vault/') && typeof route.params.id === 'string' ? route.params.id : ''
)
const detailDwellerId = computed(() => {
  const id = route.query.dweller
  return dwellerVaultId.value && typeof id === 'string' ? id : ''
})
const closeDweller = () => {
  void router.replace({ query: { ...route.query, dweller: undefined } })
}

// Deep-linked dweller chat: a non-empty `?chat=` query opens the modal while the
// underlying route stays mounted, so closing it resumes the previous view.
const chatDwellerId = computed(() => {
  const chat = route.query.chat
  return typeof chat === 'string' && chat.length > 0 ? chat : ''
})

const closeChat = () => {
  void router.replace({ query: { ...route.query, chat: undefined } })
}

// Visual effects (replaces old useFlickering)
const visualEffects = useVisualEffects()
const { isFlickeringEnabled, scanlines, glowClass, flickerOpacity } = visualEffects
watch(
  isFlickeringEnabled,
  (enabled) => {
    document.documentElement.dataset.flickering = String(enabled)
  },
  { immediate: true }
)

// Theme system
const { currentTheme, setTheme, availableThemes } = useTheme()

// Badge palette preference (colour or monochrome); applied at boot so badges
// never flash the wrong palette before the preference loads.
useBadgeStyle()

// Token refresh system (auto-refreshes tokens before expiry)
const authStore = useAuthStore()
useTokenRefresh()

// Load the profile on login, reload and account changes; clear on logout.
const profileStore = useProfileStore()
watch(
  [() => authStore.isAuthenticated, () => authStore.user?.id],
  ([authed]) => {
    if (authed) void profileStore.ensureProfileLoaded()
    else profileStore.clearProfile()
  },
  { immediate: true }
)

// Sound settings sync: hydrate from the profile and persist local changes.
useSoundProfileSync()

// Resource warnings system
useResourceWarnings()

useVaultBoyEvents(dwellerVaultId)
watch([() => authStore.token, dwellerVaultId], () => useVaultBoyFeedback().clear(), {
  flush: 'sync',
})

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

// Legacy support for old useFlickering consumers: the stored preference gated
// by prefers-reduced-motion, so reduced-motion users never start the JS loop.
provide('isFlickering', isFlickeringEnabled)
provide('toggleFlickering', visualEffects.toggleFlickering)

// Theme providers
provide('currentTheme', currentTheme)
provide('setTheme', setTheme)
provide('availableThemes', availableThemes)
</script>

<template>
  <div>
    <DefaultLayout :isFlickering="isFlickeringEnabled" :flicker-opacity="flickerOpacity">
      <router-view></router-view>
    </DefaultLayout>
    <Toaster />
    <VaultBoyFeedback
      v-if="authStore.isAuthenticated && dwellerVaultId"
      :vault-id="dwellerVaultId"
    />

    <!-- Changelog Modal (lazy: only fetched once a new version is detected) -->
    <ChangelogModal
      v-if="showChangelogModal"
      :show="showChangelogModal"
      :current-version="versionInfo.current"
      :last-seen-version="versionInfo.lastSeen ?? undefined"
      @close="hideChangelog"
      @mark-as-seen="markVersionAsSeen"
    />

    <DwellerDetailModal
      v-if="authStore.isAuthenticated && detailDwellerId"
      :key="`${dwellerVaultId}:${detailDwellerId}`"
      :dweller-id="detailDwellerId"
      :vault-id="dwellerVaultId"
      @close="closeDweller"
    />

    <!-- Dweller chat modal: deep-linked via ?chat=<dwellerId>; the underlying view stays mounted. -->
    <DwellerChatModal
      v-if="chatDwellerId"
      :key="chatDwellerId"
      :dweller-id="chatDwellerId"
      @close="closeChat"
    />

    <!-- Easter Egg Overlays -->
    <GaryOverlay :show="isGaryMode" />
    <FakeCrashOverlay :show="isCrashing" @complete="resetCrash" />
  </div>
</template>
