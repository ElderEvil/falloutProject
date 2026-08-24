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
    <div class="scanlines" aria-hidden="true"></div>
    <div class="profile-layout">
      <SidePanel :vault-id="vaultStore.activeVaultId" />
      <main class="main-content flicker pb-8" :class="{ collapsed: isCollapsed }">
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
              <BackButton label="Back to Vault" class="profile-back-button" @click="returnToVault" />
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
                        <span class="profile-status" :class="authStore.user?.email_verified ? 'profile-status--verified' : 'profile-status--unverified'">
                          <Icon :icon="authStore.user?.email_verified ? 'mdi:check-circle' : 'mdi:alert-circle-outline'" />
                          {{ authStore.user?.email_verified ? 'VERIFIED' : 'UNVERIFIED' }}
                        </span>
                        <span class="profile-status profile-status--clearance">
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
                    <RouterLink to="/preferences" class="profile-preferences-link">
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

              <section v-show="activeTab === 'ai-settings' && authStore.isSuperuser" aria-label="AI provider configuration">
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
.profile-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.main-content.collapsed {
  margin-left: 64px;
}

.profile-page .scanlines {
  opacity: 0.4;
}

.profile-page .flicker {
  animation-duration: 3.5s;
}

.profile-back-button {
  padding: 0.625rem 1.25rem;
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.5);
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

.profile-back-button:hover {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-glow);
  background: rgb(from var(--color-theme-primary) r g b / 0.08);
}

.profile-back-button:focus-visible {
  outline: 2px dashed var(--color-theme-primary);
  outline-offset: 3px;
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.profile-status,
.profile-preferences-link {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border: 1px solid;
  border-radius: 0.25rem;
  padding: 0.375rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.profile-status--verified {
  border-color: rgb(from var(--color-theme-primary) r g b / 0.3);
  background: rgb(from var(--color-theme-primary) r g b / 0.1);
  color: var(--color-theme-primary);
}

.profile-status--unverified {
  border-color: rgb(239 68 68 / 0.4);
  background: rgb(127 29 29 / 0.2);
  color: rgb(248 113 113);
}

.profile-status--clearance {
  border-color: rgb(from var(--color-theme-accent) r g b / 0.35);
  background: rgb(from var(--color-theme-accent) r g b / 0.1);
  color: var(--color-theme-accent);
}

.profile-preferences-link {
  justify-content: center;
  border-color: rgb(from var(--color-theme-primary) r g b / 0.3);
  background: var(--color-surface-raised);
  color: var(--color-theme-primary);
  text-decoration: none;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.profile-preferences-link:hover {
  background: var(--color-surface-hover);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

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

@media (max-width: 768px) {
  .main-content,
  .main-content.collapsed {
    margin-left: 0;
  }
}
</style>
