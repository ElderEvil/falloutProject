<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useProfileStore } from '../stores/profile'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { UButton, UCard } from '@/core/components/ui'
import ProfileEditor from '../components/ProfileEditor.vue'
import { LifeDeathStatistics } from '@/modules/dwellers/components/death'
import type { ProfileUpdate } from '../models/profile'
import { useWebSocket } from '@/core/composables/useWebSocket'

const router = useRouter()
const profileStore = useProfileStore()
const authStore = useAuthStore()
const isEditing = ref(false)

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

// Poll statistics every 30 seconds as a fallback
let statsInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await fetchProfile()
  await profileStore.fetchDeathStatistics()

  // Establish connection if user ID is ready
  if (wsUrl.value) {
    connect(wsUrl.value)
  }

  statsInterval = setInterval(() => {
    profileStore.fetchDeathStatistics()
  }, 30000)
})

onUnmounted(() => {
  if (statsInterval) {
    clearInterval(statsInterval)
  }
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
  console.log('Received dweller:born event:', message)
  profileStore.fetchDeathStatistics()
})

on('dweller:died', (message) => {
  console.log('Received dweller:died event:', message)
  profileStore.fetchDeathStatistics()
})

on('notification', (message) => {
  const nType = message.notification?.notification_type
  if (nType === 'baby_born' || nType === 'dweller_died') {
    console.log(`Received ${nType} notification! Refreshing stats...`)
    profileStore.fetchDeathStatistics()
  }
})

const fetchProfile = async () => {
  try {
    await profileStore.fetchProfile()
  } catch (error) {
    console.error('Failed to fetch profile:', error)
  }
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
  } catch (error) {
    console.error('Failed to update profile:', error)
  }
}

const handleAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
}

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
  <div class="min-h-screen bg-black py-8 px-4 font-mono">
    <div class="max-w-7xl mx-auto">
      <!-- Back Button -->
      <UButton variant="ghost" size="sm" class="mb-4" @click="router.push('/')">
        <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
        Back to Vault
      </UButton>

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-4xl font-bold text-theme-primary terminal-glow-subtle">OVERSEER PROFILE</h1>
        <p class="text-theme-primary/60 mt-2 uppercase tracking-wider text-sm">
          Personnel File & Vital Statistics Registry
        </p>
      </div>

      <!-- Loading State -->
      <div v-if="profileStore.loading && !profileStore.profile" class="text-center py-12">
        <Icon icon="mdi:loading" class="h-12 w-12 animate-spin text-theme-primary mx-auto" />
        <div class="text-xl text-theme-primary mt-4">Loading profile...</div>
      </div>

      <!-- Error State -->
      <UCard
        v-else-if="profileStore.error && !profileStore.profile"
        title="ERROR: PROFILE LOAD FAILURE"
        glow
        crt
      >
        <div class="text-red-500 mb-4">{{ profileStore.error }}</div>
        <UButton variant="primary" @click="fetchProfile">
          <Icon icon="mdi:refresh" class="mr-2" />
          Retry Connection
        </UButton>
      </UCard>

      <!-- Profile Content -->
      <div v-else-if="profileStore.profile" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Left Column: Personal Info -->
        <div>
          <!-- Display Mode -->
          <UCard v-if="!isEditing" title="PERSONNEL FILE" glow crt>
            <template #header>
              <UButton variant="primary" size="sm" @click="startEditing">
                <Icon icon="mdi:pencil" class="mr-1" />
                Edit
              </UButton>
            </template>

            <!-- Avatar -->
            <div class="flex justify-center mb-6">
              <div class="relative">
                <img
                  v-if="profileStore.profile.avatar_url"
                  :src="profileStore.profile.avatar_url"
                  alt="Profile avatar"
                  class="w-32 h-32 rounded-full border-2 border-theme-primary object-cover glow-pulse-subtle"
                  @error="handleAvatarError"
                />
                <div
                  v-else
                  class="w-32 h-32 rounded-full border-2 border-theme-primary bg-black flex items-center justify-center glow-pulse-subtle"
                >
                  <Icon icon="mdi:account-circle" class="text-6xl text-theme-primary/60" />
                </div>
              </div>
            </div>

            <!-- User Email -->
            <div class="mb-4">
              <label
                class="block text-xs font-medium text-theme-primary/60 uppercase tracking-wider mb-1"
                >Email Address</label
              >
              <div class="flex items-center gap-2 flex-wrap">
                <p class="text-theme-primary">
                  {{ authStore.user?.email || 'Not available' }}
                </p>
                <span
                  v-if="authStore.user?.email_verified"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-theme-primary/20 text-theme-primary border border-theme-primary/30"
                >
                  <Icon icon="mdi:check-circle" class="text-sm" />
                  VERIFIED
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-red-900/20 text-red-400 border border-red-500/30"
                >
                  <Icon icon="mdi:alert-circle-outline" class="text-sm" />
                  UNVERIFIED
                </span>
              </div>
            </div>

            <!-- Account Type -->
            <div class="mb-4">
              <label
                class="block text-xs font-medium text-theme-primary/60 uppercase tracking-wider mb-1"
                >Clearance Level</label
              >
              <div class="flex items-center gap-2">
                <span
                  v-if="authStore.isSuperuser"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
                >
                  <Icon icon="mdi:shield-crown" class="text-sm" />
                  SUPERUSER
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-theme-primary/10 text-theme-primary/80 border border-theme-primary/30"
                >
                  <Icon icon="mdi:account" class="text-sm" />
                  STANDARD
                </span>
              </div>
            </div>

            <!-- Bio -->
            <div class="mb-4">
              <label
                class="block text-xs font-medium text-theme-primary/60 uppercase tracking-wider mb-1"
                >Personnel Notes</label
              >
              <p
                class="text-theme-primary/80 whitespace-pre-wrap bg-black/40 p-3 rounded border border-theme-primary/20"
              >
                {{ profileStore.profile.bio || 'No biographical data on file.' }}
              </p>
            </div>

            <!-- Preferences -->
            <div class="mb-4">
              <label
                class="block text-xs font-medium text-theme-primary/60 uppercase tracking-wider mb-1"
                >System Preferences</label
              >
              <pre
                class="bg-black/40 p-3 rounded text-sm text-theme-primary/70 overflow-x-auto border border-theme-primary/20"
                >{{ JSON.stringify(profileStore.profile.preferences || {}, null, 2) }}</pre
              >
            </div>

            <!-- Timestamps -->
            <div
              class="text-xs text-theme-primary/40 pt-4 border-t border-theme-primary/20 font-mono"
            >
              <p>
                FILE CREATED:
                {{ formatDate(profileStore.profile.created_at) }}
              </p>
              <p>
                LAST MODIFIED:
                {{ formatDate(profileStore.profile.updated_at) }}
              </p>
            </div>
          </UCard>

          <!-- Edit Mode -->
          <ProfileEditor
            v-else
            :initial-data="profileStore.profile"
            :loading="profileStore.loading"
            :error="profileStore.error"
            @submit="handleProfileUpdate"
            @cancel="cancelEditing"
          />
        </div>

        <!-- Right Column: Statistics -->
        <div>
          <LifeDeathStatistics
            :statistics="profileStore.deathStatistics"
            :loading="profileStore.deathStatsLoading"
          />
        </div>
      </div>
    </div>
  </div>
</template>
