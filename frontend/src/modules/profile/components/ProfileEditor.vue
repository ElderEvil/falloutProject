<template>
  <div
    class="profile-editor rounded-lg border border-theme-primary/30 bg-stone-900 p-5 shadow-lg sm:p-6"
  >
    <header class="mb-6 border-b border-stone-700/80 pb-5">
      <p class="mb-1 text-xs font-semibold uppercase tracking-[0.18em] text-theme-primary">
        Vault Personnel Record
      </p>
      <h2 class="text-2xl font-bold tracking-tight text-stone-100">Edit Profile</h2>
      <p class="mt-2 max-w-xl text-sm leading-6 text-stone-400">
        Update the details other vault dwellers see when they visit your profile.
      </p>
    </header>

    <form class="space-y-5" @submit.prevent="handleSubmit">
      <div class="space-y-2">
        <div class="flex items-baseline justify-between gap-4">
          <label for="bio" class="text-sm font-semibold text-stone-200">Bio</label>
          <span class="text-xs tabular-nums text-stone-500">
            {{ formData.bio?.length || 0 }} / 500 characters
          </span>
        </div>
        <textarea
          id="bio"
          v-model="formData.bio"
          rows="4"
          maxlength="500"
          class="w-full rounded-md border border-theme-primary/30 bg-black/40 px-3 py-2.5 text-sm leading-6 text-stone-100 placeholder:text-stone-500 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
          placeholder="Share a little about yourself..."
        />
        <p class="text-xs leading-5 text-stone-500">
          A short introduction for your fellow dwellers.
        </p>
      </div>

      <div class="space-y-2">
        <label for="avatar_url" class="block text-sm font-semibold text-stone-200"
          >Avatar image</label
        >
        <input
          id="avatar_url"
          v-model="formData.avatar_url"
          type="url"
          maxlength="255"
          class="w-full rounded-md border border-theme-primary/30 bg-black/40 px-3 py-2.5 text-sm text-stone-100 placeholder:text-stone-500 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
          placeholder="https://example.com/avatar.jpg"
        />
        <p class="text-xs leading-5 text-stone-500">
          Use a direct link to a square image for the best result.
        </p>
      </div>

      <figure
        v-if="formData.avatar_url"
        class="flex items-center gap-4 rounded-md border border-stone-700 bg-black/20 p-3"
      >
        <img
          :src="formData.avatar_url"
          alt="Avatar preview"
          class="h-16 w-16 rounded-full border-2 border-theme-primary/70 object-cover shadow-[0_0_12px_var(--color-theme-glow)]"
          @error="handleImageError"
        />
        <figcaption>
          <p class="text-sm font-semibold text-stone-200">Avatar preview</p>
          <p class="mt-1 text-xs leading-5 text-stone-500">
            This is how your image will appear on your profile.
          </p>
        </figcaption>
      </figure>

      <div class="space-y-2">
        <label for="theme" class="block text-sm font-semibold text-stone-200"
          >Preferred theme</label
        >
        <select
          id="theme"
          v-model="selectedTheme"
          class="w-full rounded-md border border-theme-primary/30 bg-black/40 px-3 py-2.5 text-sm text-stone-100 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
        >
          <option v-for="theme in availableThemes" :key="theme.name" :value="theme.name">
            {{ theme.displayName }}
          </option>
        </select>
        <p class="text-xs leading-5 text-stone-500">{{ currentThemeDescription }}</p>
      </div>

      <div class="space-y-2">
        <label for="preferences" class="block text-sm font-semibold text-stone-200">
          Preferences <span class="font-normal text-stone-500">(JSON)</span>
        </label>
        <textarea
          id="preferences"
          v-model="preferencesJson"
          rows="6"
          class="w-full rounded-md border border-theme-primary/30 bg-black/40 px-3 py-2.5 font-mono text-sm leading-6 text-stone-100 placeholder:text-stone-500 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
          placeholder='{"theme": "dark", "notifications": true}'
        />
        <p class="text-xs leading-5 text-stone-500">
          Advanced settings are saved alongside your selected theme.
        </p>
        <p v-if="jsonError" class="text-xs font-medium text-danger" role="alert">
          {{ jsonError }}
        </p>
      </div>

      <div
        v-if="error"
        class="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-red-300"
        role="alert"
      >
        {{ error }}
      </div>

      <div class="flex flex-col gap-3 border-t border-stone-700/80 pt-5 sm:flex-row">
        <button
          type="submit"
          :disabled="loading"
          class="flex-1 rounded-md bg-theme-primary px-4 py-2.5 text-sm font-bold text-black transition-colors hover:bg-theme-primary/90 focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-stone-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ loading ? 'Saving...' : 'Save Changes' }}
        </button>
        <button
          type="button"
          class="flex-1 rounded-md border border-stone-600 bg-black/20 px-4 py-2.5 text-sm font-semibold text-stone-200 transition-colors hover:border-stone-500 hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-theme-primary/50 focus:ring-offset-2 focus:ring-offset-stone-900"
          @click="$emit('cancel')"
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

const { loading = false, error = null, initialData } = defineProps<Props>()

const emit = defineEmits<{
  submit: [data: ProfileUpdate]
  cancel: []
}>()

const { availableThemes, themes } = useTheme()

const formData = ref<ProfileUpdate>({
  bio: initialData.bio || '',
  avatar_url: initialData.avatar_url || '',
  preferences: initialData.preferences || {},
})

// Extract theme from preferences or use default
const selectedTheme = ref<ThemeName>((initialData.preferences?.theme as ThemeName) || 'fo4')

const currentThemeDescription = computed(() => {
  return themes[selectedTheme.value]?.description || ''
})

const preferencesJson = ref(JSON.stringify(initialData.preferences || {}, null, 2))
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
