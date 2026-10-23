<template>
  <Card class="profile-editor gap-0 border border-theme-primary/20 bg-surface p-5 ring-0 sm:p-6">
    <CardHeader class="mb-6 gap-0 border-b border-theme-primary/20 px-0 pb-5">
      <p class="mb-1 text-xs font-medium text-theme-primary/60">Your account</p>
      <CardTitle class="text-2xl font-bold tracking-tight text-theme-primary">
        Edit Profile
      </CardTitle>
      <CardDescription class="mt-2 max-w-xl text-sm leading-6 text-theme-primary/60">
        Update your account email and the details other vault dwellers see when they visit your
        profile.
      </CardDescription>
    </CardHeader>

    <CardContent class="px-0">
      <form class="space-y-5" @submit.prevent="handleSubmit">
        <div class="space-y-2">
          <Label for="username" class="text-sm font-semibold text-theme-primary/85"
            >Username</Label
          >
          <Input
            id="username"
            v-model="usernameField"
            type="text"
            maxlength="32"
            required
            class="h-auto w-full rounded-md border-theme-primary/30 bg-surface-sunken px-3 py-2.5 text-sm text-theme-primary placeholder:text-theme-primary/35"
            placeholder="Your display name"
          />
          <p v-if="usernameError" class="text-xs font-medium text-danger" role="alert">
            {{ usernameError }}
          </p>
          <p class="text-xs leading-5 text-theme-primary/50">
            3–32 characters. This is how other dwellers see you across the vault.
          </p>
        </div>

        <div class="space-y-2">
          <Label for="email" class="text-sm font-semibold text-theme-primary/85">Email</Label>
          <Input
            id="email"
            v-model="emailField"
            type="email"
            required
            class="h-auto w-full rounded-md border-theme-primary/30 bg-surface-sunken px-3 py-2.5 text-sm text-theme-primary placeholder:text-theme-primary/35"
            placeholder="overseer@vault-tec.com"
          />
          <p v-if="emailError" class="text-xs font-medium text-danger" role="alert">
            {{ emailError }}
          </p>
          <p class="text-xs leading-5 text-theme-primary/50">
            Changing this sends a verification link to the new address. Portrait, bio, and
            dweller-voice generation stay paused until it is confirmed; chat remains available.
          </p>
        </div>

        <div class="space-y-2">
          <div class="flex items-baseline justify-between gap-4">
            <Label for="bio" class="text-sm font-semibold text-theme-primary/85">Bio</Label>
            <span class="text-xs tabular-nums text-theme-primary/50">
              {{ formData.bio?.length || 0 }} / 500 characters
            </span>
          </div>
          <!-- Bio + preferences JSON stay raw <textarea>: no Textarea primitive is vendored (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
          <textarea
            id="bio"
            v-model="formData.bio"
            rows="4"
            maxlength="500"
            class="w-full rounded-md border border-theme-primary/30 bg-surface-sunken px-3 py-2.5 text-sm leading-6 text-theme-primary placeholder:text-theme-primary/35 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
            placeholder="Share a little about yourself..."
          />
          <p class="text-xs leading-5 text-theme-primary/50">
            A short introduction for your fellow dwellers.
          </p>
        </div>

        <div class="space-y-2">
          <Label for="avatar_url" class="block text-sm font-semibold text-theme-primary/85"
            >Avatar image</Label
          >
          <Input
            id="avatar_url"
            :model-value="formData.avatar_url ?? ''"
            @update:model-value="formData.avatar_url = $event"
            type="url"
            maxlength="255"
            class="h-auto w-full rounded-md border-theme-primary/30 bg-surface-sunken px-3 py-2.5 text-sm text-theme-primary placeholder:text-theme-primary/35"
            placeholder="https://example.com/avatar.jpg"
          />
          <p class="text-xs leading-5 text-theme-primary/50">
            Use a direct link to a square image for the best result.
          </p>
        </div>

        <figure
          v-if="formData.avatar_url"
          class="flex items-center gap-4 rounded-md border border-theme-primary/20 bg-surface-sunken p-3"
        >
          <img
            :src="formData.avatar_url"
            alt="Avatar preview"
            class="h-16 w-16 rounded-full border-2 border-theme-primary/30 object-cover"
            @error="handleImageError"
          />
          <figcaption>
            <p class="text-sm font-semibold text-theme-primary/85">Avatar preview</p>
            <p class="mt-1 text-xs leading-5 text-theme-primary/50">
              This is how your image will appear on your profile.
            </p>
          </figcaption>
        </figure>

        <div class="space-y-2">
          <Label for="theme" class="block text-sm font-semibold text-theme-primary/85"
            >Preferred theme</Label
          >
          <Select v-model="themeSelectModel">
            <SelectTrigger
              id="theme"
              class="w-full"
            >
              <SelectValue placeholder="Select a theme" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="theme in availableThemes" :key="theme.name" :value="theme.name">
                {{ theme.displayName }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p class="text-xs leading-5 text-theme-primary/50">{{ currentThemeDescription }}</p>
        </div>

        <details
          :open="Boolean(jsonError)"
          class="rounded-md border border-theme-primary/20 bg-surface p-3"
        >
          <summary class="cursor-pointer text-sm font-semibold text-theme-primary/75">
            Advanced preferences (JSON)
          </summary>
          <div class="mt-3 space-y-2">
            <Label for="preferences" class="block text-sm font-semibold text-theme-primary/85">
              Preferences <span class="font-normal text-theme-primary/50">(JSON)</span>
            </Label>
            <textarea
              id="preferences"
              v-model="preferencesJson"
              rows="6"
              class="w-full rounded-md border border-theme-primary/30 bg-surface-sunken px-3 py-2.5 font-mono text-sm leading-6 text-theme-primary placeholder:text-theme-primary/35 transition-colors focus:border-theme-primary focus:outline-none focus:ring-2 focus:ring-theme-primary/25"
              placeholder='{"theme": "dark", "notifications": true}'
            />
            <p class="text-xs leading-5 text-theme-primary/50">
              Advanced settings are saved alongside your selected theme.
            </p>
            <p v-if="jsonError" class="text-xs font-medium text-danger" role="alert">
              {{ jsonError }}
            </p>
          </div>
        </details>

        <Alert
          v-if="error"
          variant="destructive"
          class="rounded-md border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          {{ error }}
        </Alert>

        <div class="flex flex-col gap-3 border-t border-theme-primary/20 pt-5 sm:flex-row">
          <Button type="submit" :disabled="loading" class="w-full">
            <Icon v-if="loading" icon="mdi:loading" class="mr-1 animate-spin" />
            {{ loading ? 'Saving...' : 'Save Changes' }}
          </Button>
          <Button type="button" variant="secondary" class="w-full" @click="$emit('cancel')">
            Cancel
          </Button>
        </div>
      </form>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { ProfileUpdate } from '@/modules/profile/models/profile'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'
import type { AcceptableValue } from 'reka-ui'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
import { Alert } from '@/core/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { Icon } from '@iconify/vue'

interface Props {
  initialData: {
    bio?: string | null
    avatar_url?: string | null
    preferences?: any
  }
  username?: string | null
  email?: string | null
  loading?: boolean
  error?: string | null
}

const props = defineProps<Props>()

const { loading = false, error = null, initialData } = props

const emit = defineEmits<{
  submit: [data: ProfileUpdate, username: string | null, email: string | null]
  cancel: []
}>()

const { availableThemes, themes } = useTheme()

const formData = ref<ProfileUpdate>({
  bio: initialData.bio || '',
  avatar_url: initialData.avatar_url || '',
  preferences: initialData.preferences || {},
})

// Username lives on the auth user, not the profile. The parent (which owns the
// auth store) passes the current name and handles persisting a change.
const usernameField = ref(props.username ?? '')
const usernameError = ref<string | null>(null)

watch(usernameField, (value) => {
  if (value.length !== 0 && (value.length < 3 || value.length > 32)) {
    usernameError.value = 'Username must be between 3 and 32 characters.'
  } else {
    usernameError.value = null
  }
})

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const emailField = ref(props.email ?? '')
const emailError = ref<string | null>(null)

watch(emailField, (value) => {
  const trimmed = value.trim()
  if (trimmed.length === 0) {
    emailError.value = 'Email is required.'
  } else if (!EMAIL_PATTERN.test(trimmed)) {
    emailError.value = 'Enter a valid email address.'
  } else {
    emailError.value = null
  }
})

// Extract theme from preferences or use default
const selectedTheme = ref<ThemeName>((initialData.preferences?.theme as ThemeName) || 'fo4')

// reka-ui's Select modelValue is AcceptableValue (nullable); selectedTheme is a
// strict ThemeName union, so bridge at the Select boundary.
const themeSelectModel = computed<AcceptableValue>({
  get: () => selectedTheme.value,
  set: (value) => {
    if (typeof value === 'string') selectedTheme.value = value as ThemeName
  },
})

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
  if (jsonError.value || usernameError.value || emailError.value) {
    return
  }

  // Ensure theme is in preferences
  const updatedPreferences = {
    ...formData.value.preferences,
    theme: selectedTheme.value,
  }

  const currentUsername = props.username ?? ''
  const changedUsername =
    usernameField.value !== currentUsername && usernameField.value.trim().length > 0

  const currentEmail = props.email ?? ''
  const trimmedEmail = emailField.value.trim()
  const changedEmail = trimmedEmail.length > 0 && trimmedEmail !== currentEmail

  emit(
    'submit',
    {
      bio: formData.value.bio || null,
      avatar_url: formData.value.avatar_url || null,
      preferences: updatedPreferences,
    },
    changedUsername ? usernameField.value.trim() : null,
    changedEmail ? trimmedEmail : null
  )
}
</script>
