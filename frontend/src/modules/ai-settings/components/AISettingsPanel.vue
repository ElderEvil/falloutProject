<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useToast } from '@/core/composables/useToast'
import { UButton, UCard, UInput } from '@/core/components/ui'
import { aiSettingsService } from '../services/aiSettingsService'
import {
  AI_PROVIDER_OPTIONS,
  type AIProvider,
  type AISettingsRead,
  type AISettingsUpdate,
} from '../models/aiSettings'

const toast = useToast()

const settings = ref<AISettingsRead | null>(null)
const formProvider = ref<AIProvider | ''>('')
const formModel = ref('')
const formBaseUrl = ref('')
const formGatewayRoute = ref('')

const { run: runLoad, isLoading: isLoadingLoad } = useAsyncAction(
  async () => {
    const data = await aiSettingsService.get()
    settings.value = data
    applyProfileToForm(data)
    return data
  },
  { context: 'Failed to load AI settings', showToast: true }
)

const { run: runSave, isLoading: isLoadingSave } = useAsyncAction(
  async (payload: AISettingsUpdate) => {
    const data = await aiSettingsService.update(payload)
    settings.value = data
    applyProfileToForm(data)
    toast.success('AI configuration applied')
    return data
  },
  { context: 'Failed to save AI settings', showToast: false }
)

const { run: runReset, isLoading: isLoadingReset } = useAsyncAction(
  async () => {
    const data = await aiSettingsService.update({
      provider: null,
      model: null,
      base_url: null,
      gateway_route: null,
    })
    settings.value = data
    applyProfileToForm(data)
    toast.success('AI configuration reset to environment defaults')
    return data
  },
  { context: 'Failed to reset AI settings', showToast: false }
)

const isLoading = computed(() => isLoadingLoad.value || isLoadingSave.value || isLoadingReset.value)

function applyProfileToForm(data: AISettingsRead) {
  const profile = data.profile
  formProvider.value = profile?.provider ?? ''
  formModel.value = profile?.model ?? ''
  formBaseUrl.value = profile?.base_url ?? ''
  formGatewayRoute.value = profile?.gateway_route ?? ''
}

const dirtyPayload = computed<AISettingsUpdate>(() => {
  const profile = settings.value?.profile
  const payload: AISettingsUpdate = {}
  const currentProvider: AIProvider | null = formProvider.value === '' ? null : formProvider.value
  if (currentProvider !== (profile?.provider ?? null)) {
    payload.provider = currentProvider
  }
  const currentModel = formModel.value || null
  if (currentModel !== (profile?.model ?? null)) {
    payload.model = currentModel
  }
  const currentBaseUrl = formBaseUrl.value || null
  if (currentBaseUrl !== (profile?.base_url ?? null)) {
    payload.base_url = currentBaseUrl
  }
  const currentRoute = formGatewayRoute.value || null
  if (currentRoute !== (profile?.gateway_route ?? null)) {
    payload.gateway_route = currentRoute
  }
  return payload
})

const hasChanges = computed(() => Object.keys(dirtyPayload.value).length > 0)

async function handleSave() {
  if (!hasChanges.value) return
  await runSave(dirtyPayload.value)
}

async function handleReset() {
  await runReset()
}

onMounted(() => {
  void runLoad()
})
</script>

<template>
  <div>
    <!-- Loading State -->
    <div v-if="isLoadingLoad && !settings" class="py-20 text-center">
      <Icon icon="mdi:loading" class="mx-auto h-12 w-12 animate-spin text-theme-primary" />
      <div class="mt-4 text-xl text-theme-primary">Loading AI configuration...</div>
    </div>

    <!-- Error State -->
    <UCard
      v-else-if="!settings && !isLoadingLoad"
      title="ERROR: LOAD FAILURE"
      glow
      crt
      class="max-w-lg mx-auto"
    >
      <div class="mb-4 text-red-500">Failed to load AI settings</div>
      <UButton variant="primary" @click="runLoad">
        <Icon icon="mdi:refresh" class="mr-2" />
        Retry
      </UButton>
    </UCard>

    <!-- Main Content -->
    <div v-else-if="settings" class="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <!-- Form Card -->
      <UCard glow crt>
        <template #header>
          <div class="flex items-center gap-3">
            <Icon icon="mdi:cog-outline" class="h-6 w-6 text-theme-accent" />
            <h3 class="text-xl font-bold terminal-glow text-theme-primary">
              Provider Configuration
            </h3>
          </div>
        </template>

        <div class="space-y-5">
          <!-- Provider -->
          <div>
            <label class="block text-sm font-medium text-theme-primary/70 mb-1">
              Provider
            </label>
            <select
              v-model="formProvider"
              class="w-full rounded border-2 border-theme-primary/50 bg-surface-raised px-4 py-2 text-terminal-green transition-colors focus:border-theme-primary focus:outline-none"
            >
              <option
                v-for="opt in AI_PROVIDER_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
            <p class="mt-1 text-xs text-theme-primary/50">
              Select "Default" to use the server environment variable.
            </p>
          </div>

          <!-- Model -->
          <UInput
            v-model="formModel"
            label="Model"
            placeholder="e.g. gpt-4o-mini, claude-3-haiku, llama3"
            help-text="Leave empty to use the provider default model"
          />

          <!-- Base URL -->
          <UInput
            v-model="formBaseUrl"
            label="Base URL"
            placeholder="e.g. http://localhost:11434/v1"
            help-text="Required for Ollama / LM Studio; leave empty for cloud providers"
          />

          <!-- Gateway Route -->
          <UInput
            v-model="formGatewayRoute"
            label="Gateway Route"
            placeholder="e.g. anthropic, openai"
            help-text="Pydantic AI Gateway routing group identifier (optional)"
          />
        </div>

        <!-- Actions -->
        <div class="mt-6 flex flex-wrap items-center gap-3 border-t border-gray-700 pt-4">
          <UButton
            variant="primary"
            :disabled="!hasChanges"
            :loading="isLoadingSave"
            @click="handleSave"
          >
            <Icon icon="mdi:content-save" class="mr-1" />
            Save &amp; Apply
          </UButton>
          <UButton
            variant="danger"
            :loading="isLoadingReset"
            @click="handleReset"
          >
            <Icon icon="mdi:restore" class="mr-1" />
            Reset to Env Defaults
          </UButton>
          <span v-if="!hasChanges" class="text-xs text-theme-primary/40 italic">
            No unsaved changes
          </span>
        </div>
      </UCard>

      <!-- Effective Config Panel -->
      <UCard glow crt surface="sunken">
        <template #header>
          <div class="flex items-center gap-3">
            <Icon icon="mdi:information-outline" class="h-6 w-6 text-theme-accent" />
            <h3 class="text-xl font-bold terminal-glow text-theme-primary">
              Effective Configuration
            </h3>
          </div>
        </template>

        <div class="space-y-3 text-sm font-mono">
          <div class="effective-row">
            <span class="effective-label">Provider</span>
            <span class="effective-value">{{ settings.effective.provider }}</span>
          </div>
          <div class="effective-row">
            <span class="effective-label">Model</span>
            <span class="effective-value">{{ settings.effective.model }}</span>
          </div>
          <div class="effective-row">
            <span class="effective-label">Base URL</span>
            <span class="effective-value">{{ settings.effective.base_url || '—' }}</span>
          </div>
          <div class="effective-row">
            <span class="effective-label">Gateway Route</span>
            <span class="effective-value">{{ settings.effective.gateway_route || '—' }}</span>
          </div>
          <div class="effective-row">
            <span class="effective-label">Mode</span>
            <span
              class="effective-value"
              :class="{
                'text-terminal-green': settings.effective.mode !== 'disabled',
                'text-red-400': settings.effective.mode === 'disabled',
              }"
            >
              {{ settings.effective.mode }}
            </span>
          </div>
        </div>

        <div class="mt-4 border-t border-gray-700 pt-3 text-xs text-theme-primary/50">
          <Icon icon="mdi:lightbulb-outline" class="inline h-3.5 w-3.5 mr-1" />
          Reflects environment + profile overrides after last save.
        </div>
      </UCard>
    </div>
  </div>
</template>

<style scoped>
.effective-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
}

.effective-label {
  color: var(--color-theme-primary);
  opacity: 0.6;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
}

.effective-value {
  color: var(--color-theme-primary);
  text-align: right;
  word-break: break-all;
}
</style>