<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { Alert, AlertDescription } from '@/core/components/ui/alert'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { LifeDeathStatistics } from '@/modules/dwellers/components/death'
import { usePolling } from '@/core/composables/usePolling'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useBackNavigation } from '@/core/composables/useBackNavigation'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useProfileStore } from '../stores/profile'
import ProfileEditor from '../components/ProfileEditor.vue'
import AIUsageCard from '../components/AIUsageCard.vue'
import VaultOperationsCard from '../components/VaultOperationsCard.vue'
import AISettingsPanel from '@/modules/ai-settings/components/AISettingsPanel.vue'
import type { ProfileUpdate } from '../models/profile'

const profileStore = useProfileStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const backNav = useBackNavigation('User Profile', () =>
  vaultStore.activeVaultId ? `/vault/${vaultStore.activeVaultId}` : '/'
)
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

// Poll statistics every 30 seconds. The polling composable
// automatically pauses when this view's scope is disposed.
usePolling(
  async () => {
    await Promise.all([
      profileStore.refreshProfile(),
      profileStore.fetchDeathStatistics(),
      profileStore.fetchAIUsage(),
    ])
  },
  { interval: 30_000, immediate: false }
)

onMounted(async () => {
  await fetchProfile()
  await profileStore.fetchDeathStatistics()
  await profileStore.fetchAIUsage()
})

const fetchProfile = async () => {
  try {
    await profileStore.fetchProfile()
  } catch {}
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
</script>

<template>
  <div
    class="profile-page relative min-h-screen bg-terminal-background font-mono text-theme-primary [text-shadow:none]"
  >
    <div class="flex min-h-screen">
      <SidePanel :vault-id="vaultStore.activeVaultId" />
      <main
        class="flex-1 pb-8 transition-[margin-left] duration-300 ease max-md:ml-0"
        :class="isCollapsed ? 'ml-16' : 'ml-60'"
      >
        <PageContentRail>
          <PageHeader
            title="User Profile"
            icon="mdi:badge-account-horizontal-outline"
            subtitle="Identity, account status, and vault record."
          >
            <template #back>
              <PageNavigation
                :back-label="backNav.backLabel()"
                :back-to="backNav.backTo()"
                :breadcrumbs="backNav.breadcrumbs()"
              />
            </template>
          </PageHeader>

          <div v-if="profileStore.loading && !profileStore.profile" class="py-20 text-center">
            <Icon icon="mdi:loading" class="mx-auto h-12 w-12 animate-spin text-theme-primary" />
            <div class="mt-4 text-xl text-theme-primary">Loading your profile...</div>
          </div>

          <Card
            v-else-if="profileStore.error && !profileStore.profile"
            class="gap-0 border-theme-primary/20 bg-surface"
          >
            <CardHeader class="border-b border-theme-primary/20 pb-4">
              <CardTitle class="text-xl font-bold text-theme-primary">Profile unavailable</CardTitle>
            </CardHeader>
            <CardContent class="pt-4">
              <Alert variant="destructive" class="mb-4">
                <AlertDescription>{{ profileStore.error }}</AlertDescription>
              </Alert>
              <Button variant="default" @click="fetchProfile">
                <Icon icon="mdi:refresh" class="mr-2" />
                Retry Connection
              </Button>
            </CardContent>
          </Card>

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
              <Tabs
                :model-value="activeTab"
                class="mb-6"
                @update:model-value="activeTab = String($event)"
              >
                <TabsList>
                  <TabsTrigger v-for="tab in tabs" :key="tab.key" :value="tab.key">
                    {{ tab.label }}
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <section v-show="activeTab === 'dossier'">
                <Card class="profile-dossier gap-0 border-theme-primary/20 bg-surface">
                  <CardHeader class="pb-5">
                    <CardTitle class="text-xl font-bold text-theme-primary">User profile</CardTitle>
                    <CardDescription>Your identity and account details</CardDescription>
                    <CardAction>
                      <Button variant="outline" size="sm" @click="startEditing">
                        <Icon icon="mdi:pencil" class="mr-1" />
                        Edit profile
                      </Button>
                    </CardAction>
                  </CardHeader>

                  <CardContent class="grid gap-8 pt-0 lg:grid-cols-[minmax(0,1fr)_minmax(17rem,0.55fr)]">
                    <div class="min-w-0">
                      <div class="flex flex-col gap-6 sm:flex-row sm:items-center">
                        <div
                          class="profile-avatar flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-theme-primary/30 bg-surface-sunken"
                        >
                          <img
                            v-if="profileStore.profile.avatar_url && !avatarLoadFailed"
                            :src="profileStore.profile.avatar_url"
                            alt="Profile avatar"
                            class="h-full w-full object-cover"
                            @error="handleAvatarError"
                          />
                          <Icon
                            v-else
                            icon="mdi:account-circle"
                            class="text-6xl text-theme-primary/60"
                          />
                        </div>
                        <div class="min-w-0">
                          <p class="text-sm font-medium text-theme-primary/60">User account</p>
                          <h3 class="mt-1 truncate text-2xl font-bold text-theme-primary">
                            {{ authStore.user?.username || 'User' }}
                          </h3>
                          <p class="mt-2 break-all text-sm text-theme-primary/75">
                            {{ authStore.user?.email || 'No account email on file' }}
                          </p>
                          <div class="mt-3 flex flex-wrap gap-2">
                            <Badge
                              :variant="authStore.user?.email_verified ? 'default' : 'destructive'"
                              class="gap-1.5 font-medium"
                            >
                              <Icon
                                :icon="
                                  authStore.user?.email_verified
                                    ? 'mdi:check-circle'
                                    : 'mdi:alert-circle-outline'
                                "
                              />
                              {{ authStore.user?.email_verified ? 'Verified' : 'Unverified' }}
                            </Badge>
                            <Badge
                              :variant="authStore.isSuperuser ? 'secondary' : 'outline'"
                              class="gap-1.5 font-medium"
                            >
                              <Icon
                                :icon="authStore.isSuperuser ? 'mdi:shield-crown' : 'mdi:account'"
                              />
                              {{ authStore.isSuperuser ? 'Administrator' : 'Standard account' }}
                            </Badge>
                          </div>
                        </div>
                      </div>

                      <section class="mt-8">
                        <p class="text-sm font-semibold text-theme-primary/75">Bio</p>
                        <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-theme-primary/85">
                          {{ profileStore.profile.bio || 'No bio added yet.' }}
                        </p>
                      </section>
                    </div>

                    <aside class="rounded-md border border-theme-primary/15 bg-surface-sunken p-5">
                      <h3 class="text-sm font-semibold text-theme-primary">Account details</h3>
                      <dl class="mt-5 space-y-4 text-sm">
                        <div>
                          <dt class="text-theme-primary/60">Joined</dt>
                          <dd class="mt-1 text-theme-primary/85">{{ formatDate(profileStore.profile.created_at) }}</dd>
                        </div>
                        <div>
                          <dt class="text-theme-primary/60">Profile updated</dt>
                          <dd class="mt-1 text-theme-primary/85">{{ formatDate(profileStore.profile.updated_at) }}</dd>
                        </div>
                      </dl>
                      <div class="mt-6 border-t border-theme-primary/15 pt-5">
                        <p class="mb-3 text-xs leading-5 text-theme-primary/60">
                          Adjust how the app looks and behaves for your account.
                        </p>
                        <Button variant="outline" size="sm" as-child>
                          <RouterLink to="/preferences">
                            <Icon icon="mdi:tune-variant" class="mr-2" />
                            Display preferences
                          </RouterLink>
                        </Button>
                      </div>
                    </aside>
                  </CardContent>
                </Card>
              </section>

              <section
                v-show="activeTab === 'analytics'"
                aria-label="Vault analytics"
                class="grid gap-6 xl:grid-cols-2"
              >
                <VaultOperationsCard
                  class="xl:col-span-2"
                  :record="profileStore.profile"
                  :refreshing="profileStore.profileRefreshing"
                />
                <AIUsageCard
                  :stats="profileStore.aiUsageStats"
                  :loading="profileStore.aiUsageLoading"
                />
                <LifeDeathStatistics
                  :statistics="profileStore.deathStatistics"
                  :total-dwellers-created="profileStore.profile.total_dwellers_created"
                  :loading="profileStore.deathStatsLoading"
                />
              </section>

              <section
                v-if="activeTab === 'ai-settings' && authStore.isSuperuser"
                aria-label="AI provider configuration"
              >
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
/* Focus visibility for links and controls rendered by child components. */
.profile-page :deep(a:focus-visible),
.profile-page :deep(button:focus-visible),
.profile-page :deep([tabindex]:focus-visible) {
  outline: 2px dashed var(--color-theme-primary);
  outline-offset: 2px;
}

</style>
