<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import { useProfileStore } from '../stores/profile';
import { useAuthStore } from '@/modules/auth/stores/auth';
import { UButton } from '@/core/components/ui';
import ProfileEditor from '../components/ProfileEditor.vue';
import ProfileStats from '../components/ProfileStats.vue';
import type { ProfileUpdate } from '../models/profile';

const router = useRouter();
const profileStore = useProfileStore();
const authStore = useAuthStore();
const isEditing = ref(false);

onMounted(async () => {
  await fetchProfile();
});

const fetchProfile = async () => {
  try {
    await profileStore.fetchProfile();
  } catch (error) {
    console.error('Failed to fetch profile:', error);
  }
};

const startEditing = () => {
  isEditing.value = true;
  profileStore.clearError();
};

const cancelEditing = () => {
  isEditing.value = false;
  profileStore.clearError();
};

const handleProfileUpdate = async (data: ProfileUpdate) => {
  try {
    await profileStore.updateProfile(data);
    isEditing.value = false;
  } catch (error) {
    console.error('Failed to update profile:', error);
  }
};

const handleAvatarError = (event: Event) => {
  const target = event.target as HTMLImageElement;
  target.style.display = 'none';
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};
</script>

<template>
  <div class="min-h-screen bg-gray-900 py-8 px-4">
    <div class="max-w-7xl mx-auto">
      <!-- Back Button -->
      <UButton variant="ghost" size="sm" class="mb-4" @click="router.push('/')">
        <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
        Back to Vault
      </UButton>

      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-4xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">Overseer Profile</h1>
        <p class="text-gray-400 mt-2">Manage your vault overseer profile and view statistics</p>
      </div>

      <!-- Loading State -->
      <div v-if="profileStore.loading && !profileStore.profile" class="text-center py-12">
        <div class="text-xl" :style="{ color: 'var(--color-theme-primary)' }">Loading profile...</div>
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
          <div v-if="!isEditing" class="bg-gray-800 rounded-lg p-6 border"
               :style="{ borderColor: 'rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3)' }">
            <div class="flex justify-between items-start mb-6">
              <h2 class="text-2xl font-bold" :style="{ color: 'var(--color-theme-primary)' }">Personal Information</h2>
              <button
                @click="startEditing"
                class="text-black font-semibold py-2 px-4 rounded transition-colors hover:opacity-90"
                :style="{ backgroundColor: 'var(--color-theme-primary)' }"
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
                class="w-32 h-32 rounded-full border-4 object-cover"
                :style="{ borderColor: 'var(--color-theme-primary)' }"
                @error="handleAvatarError"
              />
              <div
                v-else
                class="w-32 h-32 rounded-full border-4 bg-gray-700 flex items-center justify-center"
                :style="{ borderColor: 'var(--color-theme-primary)' }"
              >
                <Icon icon="mdi:account-circle" class="text-6xl" :style="{ color: 'var(--color-theme-primary)', opacity: 0.6 }" />
              </div>
            </div>

            <!-- User Email -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-400 mb-1">Email</label>
              <div class="flex items-center gap-2 flex-wrap">
                <p class="text-white">{{ authStore.user?.email || 'Not available' }}</p>
                <span
                  v-if="authStore.user?.email_verified"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold"
                  :style="{ backgroundColor: 'rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2)', color: 'var(--color-theme-primary)' }"
                >
                  <Icon icon="mdi:check-circle" class="text-sm" />
                  VERIFIED
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-gray-700 text-gray-400"
                >
                  <Icon icon="mdi:alert-circle-outline" class="text-sm" />
                  UNVERIFIED
                </span>
              </div>
            </div>

            <!-- Account Type -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-400 mb-1">Account Type</label>
              <div class="flex items-center gap-2">
                <span
                  v-if="authStore.isSuperuser"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-yellow-500/20 text-yellow-400"
                >
                  <Icon icon="mdi:shield-crown" class="text-sm" />
                  SUPERUSER
                </span>
                <span
                  v-else
                  class="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold bg-gray-700 text-gray-300"
                >
                  <Icon icon="mdi:account" class="text-sm" />
                  STANDARD
                </span>
              </div>
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
