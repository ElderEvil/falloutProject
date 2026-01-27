<template>
  <div
    class="bg-gray-800 rounded-lg p-6 border"
    :style="{ borderColor: 'rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3)' }"
  >
    <h2 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-theme-primary)' }">
      Edit Profile
    </h2>

    <form @submit.prevent="handleSubmit" class="space-y-4">
      <!-- Bio -->
      <div>
        <label for="bio" class="block text-sm font-medium text-gray-300 mb-2"> Bio </label>
        <textarea
          id="bio"
          v-model="formData.bio"
          rows="4"
          maxlength="500"
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          placeholder="Tell us about yourself..."
        />
        <p class="text-xs text-gray-400 mt-1">{{ formData.bio?.length || 0 }} / 500 characters</p>
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
          class="w-32 h-32 rounded-full border-2 object-cover"
          :style="{ borderColor: 'var(--color-theme-primary)' }"
          @error="handleImageError"
        />
      </div>

      <!-- Theme Selector -->
      <div>
        <label for="theme" class="block text-sm font-medium text-gray-300 mb-2">
          Preferred Theme
        </label>
        <select
          id="theme"
          v-model="selectedTheme"
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
        >
          <option v-for="theme in availableThemes" :key="theme.name" :value="theme.name">
            {{ theme.displayName }}
          </option>
        </select>
        <p class="text-xs text-gray-400 mt-1">
          {{ currentThemeDescription }}
        </p>
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
          class="flex-1 text-black font-semibold py-2 px-4 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
          :style="{ backgroundColor: 'var(--color-theme-primary)' }"
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
import { ref, watch, computed } from 'vue'
import type { ProfileUpdate } from '@/modules/profile/models/profile'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'

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
  error: null,
})

const emit = defineEmits<{
  submit: [data: ProfileUpdate]
  cancel: []
}>()

const { availableThemes, themes } = useTheme()

const formData = ref<ProfileUpdate>({
  bio: props.initialData.bio || '',
  avatar_url: props.initialData.avatar_url || '',
  preferences: props.initialData.preferences || {},
})

// Extract theme from preferences or use default
const selectedTheme = ref<ThemeName>((props.initialData.preferences?.theme as ThemeName) || 'fo4')

const currentThemeDescription = computed(() => {
  return themes[selectedTheme.value]?.description || ''
})

const preferencesJson = ref(JSON.stringify(props.initialData.preferences || {}, null, 2))
const jsonError = ref<string | null>(null)

// Watch for theme changes and update preferences
watch(selectedTheme, (newTheme) => {
  formData.value.preferences = {
    ...formData.value.preferences,
    theme: newTheme,
  }
  // Update the JSON editor to reflect the theme change
  preferencesJson.value = JSON.stringify(formData.value.preferences, null, 2)
})

// Watch for preferences JSON changes and validate
watch(preferencesJson, (newValue) => {
  try {
    const parsed = JSON.parse(newValue)
    formData.value.preferences = parsed
    // Update selectedTheme if it changed in JSON
    if (parsed.theme && parsed.theme !== selectedTheme.value) {
      selectedTheme.value = parsed.theme
    }
    jsonError.value = null
  } catch (e) {
    jsonError.value = 'Invalid JSON format'
  }
})

const handleImageError = () => {
  // Could show a placeholder or error message
}

const handleSubmit = () => {
  if (jsonError.value) {
    return
  }

  // Ensure theme is in preferences
  const updatedPreferences = {
    ...formData.value.preferences,
    theme: selectedTheme.value,
  }

  emit('submit', {
    bio: formData.value.bio || null,
    avatar_url: formData.value.avatar_url || null,
    preferences: updatedPreferences,
  })
}
</script>
