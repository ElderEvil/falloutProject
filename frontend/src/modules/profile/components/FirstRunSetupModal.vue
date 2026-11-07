<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useProfileStore } from '../stores/profile'
import { SETUP_PREFERENCE_VERSION } from '../models/setup'
import ThemePicker from './ThemePicker.vue'
import SoundSettingsPanel from './SoundSettingsPanel.vue'

const emit = defineEmits<{ complete: [] }>()

const profileStore = useProfileStore()
const { currentTheme, setTheme } = useTheme()
const selectedTheme = ref<ThemeName>(currentTheme.value.name)
const saving = ref(false)
const saveError = ref('')

const selectTheme = (theme: ThemeName) => {
  selectedTheme.value = theme
  setTheme(theme)
  void profileStore
    .savePreferences({ theme })
    .catch((error: unknown) => handleStoreError(error, 'Failed to save theme preference'))
}

const finish = async (skipped: boolean) => {
  if (saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    await profileStore.savePreferences({
      setup: { version: SETUP_PREFERENCE_VERSION, completed: true, skipped },
    })
    emit('complete')
  } catch (error) {
    saveError.value = 'Could not save this setup. Try again.'
    handleStoreError(error, 'Failed to save first-run setup')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <TerminalModal
    :open="true"
    title="Welcome, Overseer"
    icon="mdi:account-star"
    size="3xl"
    max-height="90"
    @close="finish(true)"
  >
    <div class="min-h-0 flex-1 space-y-6 overflow-y-auto p-6 text-theme-primary">
      <p class="text-sm leading-relaxed text-theme-primary/75">
        Before you commission your first vault, choose how your terminal looks and sounds. You can
        change both later in Preferences.
      </p>

      <section aria-labelledby="setup-theme-heading">
        <h3
          id="setup-theme-heading"
          class="mb-1 text-sm font-bold uppercase tracking-wider text-theme-accent"
        >
          Terminal theme
        </h3>
        <p class="mb-3 text-xs text-theme-primary/60">
          Pick the palette you will see throughout the vault.
        </p>
        <ThemePicker :model-value="selectedTheme" @update:model-value="selectTheme" />
      </section>

      <section aria-labelledby="setup-audio-heading">
        <h3
          id="setup-audio-heading"
          class="mb-1 text-sm font-bold uppercase tracking-wider text-theme-accent"
        >
          Audio
        </h3>
        <p class="mb-1 text-xs text-theme-primary/60">
          Sound is off by default. Enabling it here also unlocks browser audio for this session.
        </p>
        <SoundSettingsPanel />
      </section>

      <p v-if="saveError" role="alert" class="flex items-center gap-2 text-sm text-danger">
        <Icon icon="mdi:alert-circle-outline" />
        {{ saveError }}
      </p>
    </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="Skip for now"
        :confirm-label="saving ? 'Saving...' : 'Continue'"
        confirm-icon="mdi:arrow-right"
        :confirm-disabled="saving"
        @cancel="finish(true)"
        @confirm="finish(false)"
      />
    </template>
  </TerminalModal>
</template>
