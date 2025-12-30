<template>
  <div class="bg-gray-800 rounded-lg p-6 border border-green-500/30">
    <h2 class="text-2xl font-bold text-green-500 mb-6">Edit Profile</h2>

    <form @submit.prevent="handleSubmit" class="space-y-4">
      <!-- Bio -->
      <div>
        <label for="bio" class="block text-sm font-medium text-gray-300 mb-2">
          Bio
        </label>
        <textarea
          id="bio"
          v-model="formData.bio"
          rows="4"
          maxlength="500"
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          placeholder="Tell us about yourself..."
        />
        <p class="text-xs text-gray-400 mt-1">
          {{ formData.bio?.length || 0 }} / 500 characters
        </p>
      </div>

      <!-- Avatar URL -->
      <div>
        <label for="avatar_url" class="block text-sm font-medium text-gray-300 mb-2">
          Avatar URL
        </label>
        <input
          id="avatar_url"
          v-model="formData.avatar_url"
          type="url"
          maxlength="255"
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          placeholder="https://example.com/avatar.jpg"
        />
      </div>

      <!-- Avatar Preview -->
      <div v-if="formData.avatar_url" class="flex justify-center">
        <img
          :src="formData.avatar_url"
          alt="Avatar preview"
          class="w-32 h-32 rounded-full border-2 border-green-500 object-cover"
          @error="handleImageError"
        />
      </div>

      <!-- Preferences (JSON editor) -->
      <div>
        <label for="preferences" class="block text-sm font-medium text-gray-300 mb-2">
          Preferences (JSON)
        </label>
        <textarea
          id="preferences"
          v-model="preferencesJson"
          rows="6"
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent font-mono text-sm"
          placeholder='{"theme": "dark", "notifications": true}'
        />
        <p v-if="jsonError" class="text-xs text-red-500 mt-1">
          {{ jsonError }}
        </p>
      </div>

      <!-- Error Message -->
      <div v-if="error" class="text-red-500 text-sm">
        {{ error }}
      </div>

      <!-- Action Buttons -->
      <div class="flex gap-3 pt-4">
        <button
          type="submit"
          :disabled="loading"
          class="flex-1 bg-green-500 hover:bg-green-600 text-black font-semibold py-2 px-4 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? 'Saving...' : 'Save Changes' }}
        </button>
        <button
          type="button"
          @click="$emit('cancel')"
          class="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-2 px-4 rounded transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ProfileUpdate } from '@/models/profile'

interface Props {
  initialData: {
    bio?: string | null
    avatar_url?: string | null
    preferences?: any
  }
  loading?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null
})

const emit = defineEmits<{
  submit: [data: ProfileUpdate]
  cancel: []
}>()

const formData = ref<ProfileUpdate>({
  bio: props.initialData.bio || '',
  avatar_url: props.initialData.avatar_url || '',
  preferences: props.initialData.preferences || {}
})

const preferencesJson = ref(JSON.stringify(props.initialData.preferences || {}, null, 2))
const jsonError = ref<string | null>(null)

// Watch for preferences JSON changes and validate
watch(preferencesJson, (newValue) => {
  try {
    const parsed = JSON.parse(newValue)
    formData.value.preferences = parsed
    jsonError.value = null
  } catch (e) {
    jsonError.value = 'Invalid JSON format'
  }
})

const handleImageError = () => {
  // Could show a placeholder or error message
  console.warn('Failed to load avatar image')
}

const handleSubmit = () => {
  if (jsonError.value) {
    return
  }

  emit('submit', {
    bio: formData.value.bio || null,
    avatar_url: formData.value.avatar_url || null,
    preferences: formData.value.preferences
  })
}
</script>
