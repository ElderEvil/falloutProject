<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { UButton, UCard, UTabs } from '@/core/components/ui'
import { LifeDeathStatistics } from '@/modules/dwellers/components/death'
import { useWebSocket } from '@/core/composables/useWebSocket'
import { usePolling } from '@/core/composables/usePolling'
import { useSidePanel } from '@/core/composables/useSidePanel'
import BackButton from '@/core/components/common/BackButton.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import { useProfileStore } from '../stores/profile'
import ProfileEditor from '../components/ProfileEditor.vue'
import AIUsageCard from '../components/AIUsageCard.vue'
import AISettingsPanel from '@/modules/ai-settings/components/AISettingsPanel.vue'
import type { ProfileUpdate } from '../models/profile'

const router = useRouter()
const profileStore = useProfileStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const isEditing = ref(false)
const avatarLoadFailed = ref(false)
const activeTab = ref('dossier')

const tabs = computed(() => {
  const baseTabs = [
    { key: 'dossier', label: 'Dossier' },
    { key: 'analytics', label: 'Vault Analytics' },
  ]
  if (authStore.isSuperuser) {
    baseTabs.push({ key: 'ai-settings', label: 'AI Settings' })
  }
  return baseTabs
})

watch(
  () => authStore.isSuperuser,
  (isSuperuser) => {
    if (!isSuperuser && activeTab.value === 'ai-settings') {
      activeTab.value = 'dossier'
    }
  }
)
const { isCollapsed } = useSidePanel()

// WebSocket for real-time statistical updates
// Derive scheme and host from page origin for proper HTTPS/WSS support
const wsUrl = computed(() => {
  if (!authStore.user?.id) return ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/v1/ws/${authStore.user.id}`
})

// Register WebSocket composable at setup top-level to avoid lifecycle warning
const { connect, on, disconnect } = useWebSocket()

// Poll statistics every 30 seconds as a fallback. The polling composable
// automatically pauses when this view's scope is disposed.
usePolling(
  async () => {
    await Promise.all([profileStore.fetchDeathStatistics(), profileStore.fetchAIUsage()])
  },
  { interval: 30_000, immediate: false }
)

onMounted(async () => {
  await fetchProfile()
  await profileStore.fetchDeathStatistics()
  await profileStore.fetchAIUsage()

  if (wsUrl.value) {
    connect(wsUrl.value)
  }
})

onUnmounted(() => {
  // Properly close WebSocket connection
  disconnect()
})

// Watch for user ID changes and reconnect with proper URL
watch(wsUrl, (newUrl, oldUrl) => {
  if (newUrl && newUrl !== oldUrl) {
    disconnect()
    connect(newUrl)
  }
})

// Watcher to handle cases where user ID arrives late or changes
watch(
  () => wsUrl.value,
  (newUrl) => {
    if (newUrl) {
      connect()
    } else {
      disconnect()
    }
  }
)

// Register listeners
on('dweller:born', (message) => {
  profileStore.fetchDeathStatistics()
})

on('dweller:died', (message) => {
  profileStore.fetchDeathStatistics()
})

on('notification', (message) => {
  const nType = message.notification?.notification_type
  if (nType === 'baby_born' || nType === 'dweller_died') {
    profileStore.fetchDeathStatistics()
  }
})

const fetchProfile = async () => {
  try {
    await profileStore.fetchProfile()
  } catch {}
}

const returnToVault = () => {
  void router.push(vaultStore.activeVaultId ? `/vault/${vaultStore.activeVaultId}` : '/')
}

const startEditing = () => {
  isEditing.value = true
  profileStore.clearError()
}

const cancelEditing = () => {
  isEditing.value = false
  profileStore.clearError()
}

const handleProfileUpdate = async (data: ProfileUpdate) => {
  try {
    await profileStore.updateProfile(data)
    isEditing.value = false
  } catch {}
}

const handleAvatarError = () => {
  avatarLoadFailed.value = true
}

watch(
  () => profileStore.profile?.avatar_url,
  () => {
    avatarLoadFailed.value = false
  }
)

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const hasVaultRecord = computed(() => {
  const p = profileStore.profile
  if (!p) return false
  return (
    p.total_dwellers_created > 0 ||
    p.total_caps_earned > 0 ||
    p.total_explorations > 0 ||
    p.total_rooms_built > 0
  )
})
</script>

<template>
  <div class="profile-page relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="scanlines opacity-40" aria-hidden="true"></div>
    <div class="flex min-h-screen">
      <SidePanel />
      <main
        class="flex-1 flicker pb-8 transition-[margin-left] duration-300 ease [animation-duration:3.5s] max-md:ml-0"
        :class="isCollapsed ? 'ml-16' : 'ml-60'"
      >
        <PageContentRail>
          <nav class="profile-breadcrumb mb-3 flex items-center gap-2 font-mono text-sm tracking-wider">
            <span class="text-theme-primary/70">VAULTS</span>
            <Icon icon="mdi:chevron-right" class="h-4 w-4 text-theme-primary/50" :ariaHidden="true" />
            <span class="text-theme-primary">OVERSEER PROFILE</span>
          </nav>

          <PageHeader
            title="Overseer Profile"
            icon="mdi:badge-account-horizontal-outline"
            subtitle="Identity, account status, and vault record."
          >
            <template #back>
              <BackButton
                label="Back to Vault"
                class="inline-flex items-center gap-1.5 px-5 py-2.5 text-[0.95rem] font-bold tracking-[0.08em] border border-theme-primary/50 rounded transition-all duration-200 hover:border-theme-primary hover:bg-theme-primary/10 hover:shadow-[0_0_12px_var(--color-theme-glow)] focus-visible:outline-2 focus-visible:outline-dashed focus-visible:outline-offset-[3px] focus-visible:outline-theme-primary focus-visible:shadow-[0_0_12px_var(--color-theme-glow)]"
                @click="returnToVault"
              />
            </template>
          </PageHeader>

          <div v-if="profileStore.loading && !profileStore.profile" class="py-20 text-center">
            <Icon icon="mdi:loading" class="mx-auto h-12 w-12 animate-spin text-theme-primary" />
            <div class="mt-4 text-xl text-theme-primary">Loading personnel record...</div>
          </div>

          <UCard v-else-if="profileStore.error && !profileStore.profile" title="ERROR: PROFILE LOAD FAILURE" glow crt>
            <div class="mb-4 text-red-500">{{ profileStore.error }}</div>
            <UButton variant="primary" @click="fetchProfile">
              <Icon icon="mdi:refresh" class="mr-2" />
              Retry Connection
            </UButton>
          </UCard>

          <div v-else-if="profileStore.profile" class="space-y-6">
            <ProfileEditor
              v-if="isEditing"
              :initial-data="profileStore.profile"
              :loading="profileStore.loading"
              :error="profileStore.error"
              @submit="handleProfileUpdate"
              @cancel="cancelEditing"
            />

            <template v-else>
              <UTabs v-model="activeTab" :tabs="tabs" class="mb-6" />

              <div v-show="activeTab === 'dossier'" class="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.65fr)]">
                <UCard glow crt class="profile-dossier">
                  <template #header>
                    <div class="flex items-center justify-between gap-3">
                      <div class="flex items-center gap-3">
                        <Icon icon="mdi:folder-account-outline" class="h-6 w-6 text-theme-accent" />
                        <div>
                          <p class="text-sm font-bold tracking-[0.16em] text-theme-primary/75">PERSONNEL FILE</p>
                          <h2 class="text-xl font-bold text-theme-primary terminal-glow">OVERSEER DOSSIER</h2>
                        </div>
                      </div>
                      <UButton variant="secondary" size="sm" @click="startEditing">
                        <Icon icon="mdi:pencil" class="mr-1" />
                        Edit profile
                      </UButton>
                    </div>
                  </template>

                  <div class="flex flex-col gap-6 sm:flex-row sm:items-center">
                    <div class="profile-avatar flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-theme-primary bg-surface-sunken shadow-[0_0_18px_var(--color-theme-glow)]">
                      <img
                        v-if="profileStore.profile.avatar_url && !avatarLoadFailed"
                        :src="profileStore.profile.avatar_url"
                        alt="Profile avatar"
                        class="h-full w-full object-cover"
                        @error="handleAvatarError"
                      />
                      <Icon v-else icon="mdi:account-circle" class="text-6xl text-theme-primary/60" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-sm font-bold tracking-[0.16em] text-theme-accent">VAULT-TEC OVERSEER</p>
                      <h3 class="mt-1 truncate text-2xl font-bold text-theme-primary terminal-glow">
                        {{ authStore.user?.username || 'Vault Overseer' }}
                      </h3>
                      <p class="mt-2 break-all text-sm text-theme-primary/75">{{ authStore.user?.email || 'No account email on file' }}</p>
                      <div class="mt-3 flex flex-wrap gap-2">
                        <span class="inline-flex items-center gap-1.5 border rounded px-2 py-1.5 text-xs font-bold tracking-[0.08em]" :class="authStore.user?.email_verified ? 'border-theme-primary/30 bg-theme-primary/10 text-theme-primary' : 'border-red-500/40 bg-red-900/20 text-red-400'">
                          <Icon :icon="authStore.user?.email_verified ? 'mdi:check-circle' : 'mdi:alert-circle-outline'" />
                          {{ authStore.user?.email_verified ? 'VERIFIED' : 'UNVERIFIED' }}
                        </span>
                        <span class="inline-flex items-center gap-1.5 border rounded px-2 py-1.5 text-xs font-bold tracking-[0.08em] border-theme-accent/35 bg-theme-accent/10 text-theme-accent">
                          <Icon :icon="authStore.isSuperuser ? 'mdi:shield-crown' : 'mdi:account'" />
                          {{ authStore.isSuperuser ? 'ADMIN CLEARANCE' : 'STANDARD CLEARANCE' }}
                        </span>
                      </div>
                    </div>
                  </div>

                  <section class="mt-6 border-t border-theme-primary/20 pt-5">
                    <p class="text-sm font-bold tracking-[0.16em] text-theme-primary/75">PERSONNEL NOTES</p>
                    <p class="mt-2 whitespace-pre-wrap rounded border border-theme-primary/20 bg-surface-sunken p-4 text-sm leading-6 text-theme-primary/85">
                      {{ profileStore.profile.bio || 'No biographical data on file.' }}
                    </p>
                  </section>

                  <div class="mt-5 flex flex-col gap-3 border-t border-theme-primary/20 pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <div class="text-sm leading-6 text-theme-primary/75">
                      <p>FILE CREATED: {{ formatDate(profileStore.profile.created_at) }}</p>
                      <p>LAST MODIFIED: {{ formatDate(profileStore.profile.updated_at) }}</p>
                    </div>
                    <RouterLink
                      to="/preferences"
                      class="inline-flex items-center justify-center gap-1.5 border rounded px-2 py-1.5 text-xs font-bold tracking-[0.08em] border-theme-primary/30 bg-surface-raised text-theme-primary no-underline transition-colors duration-200 hover:bg-surface-hover hover:shadow-[0_0_10px_var(--color-theme-glow)]"
                    >
                      <Icon icon="mdi:tune-variant" />
                      Manage display preferences
                    </RouterLink>
                  </div>
                </UCard>

                <UCard title="VAULT RECORD" glow crt>
                  <p class="mb-4 text-sm leading-5 text-theme-primary/70">Lifetime results associated with this overseer account.</p>
                  <div v-if="hasVaultRecord" class="grid grid-cols-2 gap-3">
                    <TerminalMetric icon="mdi:account-group" label="Dwellers" :value="profileStore.profile.total_dwellers_created" compact />
                    <TerminalMetric icon="mdi:currency-usd" label="Caps" :value="profileStore.profile.total_caps_earned" tone="caps" compact />
                    <TerminalMetric icon="mdi:compass" label="Explorations" :value="profileStore.profile.total_explorations" compact />
                    <TerminalMetric icon="mdi:office-building" label="Rooms built" :value="profileStore.profile.total_rooms_built" compact />
                  </div>
                  <p v-else class="py-6 text-center text-sm text-theme-primary/70">No activity recorded yet.</p>
                </UCard>
              </div>

              <section v-show="activeTab === 'analytics'" aria-label="Vault analytics" class="grid gap-6 xl:grid-cols-2">
                <AIUsageCard :stats="profileStore.aiUsageStats" :loading="profileStore.aiUsageLoading" />
                <LifeDeathStatistics :statistics="profileStore.deathStatistics" :loading="profileStore.deathStatsLoading" />
              </section>

              <section v-if="activeTab === 'ai-settings' && authStore.isSuperuser" aria-label="AI provider configuration">
                <AISettingsPanel />
              </section>
            </template>
          </div>
        </PageContentRail>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Accessibility-only rules that cannot be expressed as Tailwind utilities:
   - `:deep` focus-visible rings for elements inside child components
   - reduced-motion opt-out for the CRT scanline/flicker effects */
.profile-page :deep(a:focus-visible),
.profile-page :deep(button:focus-visible),
.profile-page :deep([tabindex]:focus-visible) {
  outline: 2px dashed var(--color-theme-primary);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .profile-page .scanlines {
    display: none;
  }

  .profile-page .flicker {
    animation: none;
  }

  .profile-page .terminal-glow {
    text-shadow: 0 0 4px var(--color-theme-primary);
  }
}
</style>
