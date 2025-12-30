<template>
  <div class="min-h-screen bg-gray-900 py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-4xl font-bold text-green-500">Overseer Profile</h1>
        <p class="text-gray-400 mt-2">Manage your vault overseer profile and view statistics</p>
      </div>

      <!-- Loading State -->
      <div v-if="profileStore.loading && !profileStore.profile" class="text-center py-12">
        <div class="text-green-500 text-xl">Loading profile...</div>
      </div>

      <!-- Error State -->
      <div
        v-else-if="profileStore.error && !profileStore.profile"
        class="bg-red-900/20 border border-red-500 rounded-lg p-6"
      >
        <h3 class="text-red-500 font-semibold text-lg mb-2">Error Loading Profile</h3>
        <p class="text-gray-300">{{ profileStore.error }}</p>
        <button
          @click="fetchProfile"
          class="mt-4 bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded transition-colors"
        >
          Retry
        </button>
      </div>

      <!-- Profile Content -->
      <div v-else-if="profileStore.profile" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Left Column: Personal Info -->
        <div>
          <!-- Display Mode -->
          <div v-if="!isEditing" class="bg-gray-800 rounded-lg p-6 border border-green-500/30">
            <div class="flex justify-between items-start mb-6">
              <h2 class="text-2xl font-bold text-green-500">Personal Information</h2>
              <button
                @click="startEditing"
                class="bg-green-500 hover:bg-green-600 text-black font-semibold py-2 px-4 rounded transition-colors"
              >
                Edit Profile
              </button>
            </div>

            <!-- Avatar -->
            <div class="flex justify-center mb-6">
              <img
                v-if="profileStore.profile.avatar_url"
                :src="profileStore.profile.avatar_url"
                alt="Profile avatar"
                class="w-32 h-32 rounded-full border-4 border-green-500 object-cover"
                @error="handleAvatarError"
              />
              <div
                v-else
                class="w-32 h-32 rounded-full border-4 border-green-500 bg-gray-700 flex items-center justify-center"
              >
                <span class="text-4xl text-green-500">👤</span>
              </div>
            </div>

            <!-- User Email -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-400 mb-1">Email</label>
              <p class="text-white">{{ authStore.user?.email || 'Not available' }}</p>
            </div>

            <!-- Bio -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-400 mb-1">Bio</label>
              <p class="text-white whitespace-pre-wrap">
                {{ profileStore.profile.bio || 'No bio provided yet.' }}
              </p>
            </div>

            <!-- Preferences -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-400 mb-1">Preferences</label>
              <pre
                class="bg-gray-700 p-3 rounded text-sm text-gray-300 overflow-x-auto"
              >{{ JSON.stringify(profileStore.profile.preferences || {}, null, 2) }}</pre>
            </div>

            <!-- Timestamps -->
            <div class="text-xs text-gray-500 pt-4 border-t border-gray-700">
              <p>Created: {{ formatDate(profileStore.profile.created_at) }}</p>
              <p>Updated: {{ formatDate(profileStore.profile.updated_at) }}</p>
            </div>
          </div>

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
          <ProfileStats :statistics="profileStore.statistics" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useProfileStore } from '@/stores/profile'
import { useAuthStore } from '@/stores/auth'
import ProfileEditor from '@/components/profile/ProfileEditor.vue'
import ProfileStats from '@/components/profile/ProfileStats.vue'
import type { ProfileUpdate } from '@/models/profile'

const profileStore = useProfileStore()
const authStore = useAuthStore()
const isEditing = ref(false)

onMounted(async () => {
  await fetchProfile()
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
    minute: '2-digit'
  })
}
</script>
