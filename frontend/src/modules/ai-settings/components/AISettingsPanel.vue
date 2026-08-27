<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useToast } from '@/core/composables/useToast'
import { UButton, UCard, UInput } from '@/core/components/ui'
import { aiSettingsService } from '../services/aiSettingsService'
import {
  AI_PROVIDER_OPTIONS,
  type AIProvider,
  type AISettingsRead,
  type AISettingsTestResult,
  type AISettingsUpdate,
} from '../models/aiSettings'

const toast = useToast()

const settings = ref<AISettingsRead | null>(null)
const formProvider = ref<AIProvider | ''>('')
const formModel = ref('')
const formBaseUrl = ref('')
const formGatewayRoute = ref('')
const testResult = ref<AISettingsTestResult | null>(null)
const resetArmed = ref(false)
const copiedConfig = ref(false)

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

const { run: runTest, isLoading: isLoadingTest } = useAsyncAction(
  async (payload: AISettingsUpdate) => {
    const result = await aiSettingsService.test(payload)
    testResult.value = result
    return result
  },
  { context: 'Failed to test AI connection', showToast: false }
)

const isLoading = computed(
  () => isLoadingLoad.value || isLoadingSave.value || isLoadingReset.value || isLoadingTest.value
)

function applyProfileToForm(data: AISettingsRead) {
  const profile = data.profile
  formProvider.value = profile?.provider ?? ''
  formModel.value = profile?.model ?? ''
  formBaseUrl.value = profile?.base_url ?? ''
  formGatewayRoute.value = profile?.gateway_route ?? ''
  testResult.value = null
}

watch([formProvider, formModel, formBaseUrl, formGatewayRoute], () => {
  testResult.value = null
})

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

const showBaseUrlField = computed(() => {
  const provider = formProvider.value
  return provider === '' || provider === 'ollama' || provider === 'lmstudio'
})

const baseUrlRequired = computed(() => {
  const provider = formProvider.value
  return provider === 'ollama' || provider === 'lmstudio'
})

const baseUrlConnected = computed(() => testResult.value?.status === 'ok')

const providerHelperText = computed(() => {
  const provider = formProvider.value
  if (provider === '') return 'Default uses the server environment variable.'
  if (provider === 'ollama' || provider === 'lmstudio')
    return 'Local provider — Base URL is required.'
  return 'Cloud provider — Base URL is not needed.'
})

async function handleSave() {
  if (!hasChanges.value) return
  await runSave(dirtyPayload.value)
}

async function handleTest() {
  testResult.value = null
  await runTest(dirtyPayload.value)
}

async function handleReset() {
  if (!resetArmed.value) {
    resetArmed.value = true
    return
  }
  await runReset()
  resetArmed.value = false
}

async function handleCopyConfig() {
  if (!settings.value) return
  const eff = settings.value.effective
  const text = [
    `Provider: ${eff.provider}`,
    `Model: ${eff.model}`,
    `Base URL: ${eff.base_url || '—'}`,
    `Gateway Route: ${eff.gateway_route || '—'}`,
    `Mode: ${eff.mode}`,
  ].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copiedConfig.value = true
    setTimeout(() => {
      copiedConfig.value = false
    }, 2000)
  } catch {
    toast.error('Failed to copy configuration')
  }
}

function getProvenance(field: 'provider' | 'model' | 'base_url' | 'gateway_route'): string {
  if (!settings.value) return 'env'
  const profile = settings.value.profile
  const effective = settings.value.effective
  const profileValue = profile?.[field]
  const effectiveValue = effective[field]
  if (profileValue !== null && profileValue !== undefined && profileValue === effectiveValue) {
    return 'profile'
  }
  return 'env'
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
              <span class="text-xs text-theme-primary/50 font-normal ml-1">(Optional)</span>
            </label>
            <select
              v-model="formProvider"
              class="focus-visible:outline-none focus-visible:border-theme-primary focus-visible:shadow-[0_0_0_2px_var(--color-theme-glow)] w-full rounded border-2 border-theme-primary/50 bg-surface-raised px-4 py-2 text-terminal-green transition-colors"
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
              {{ providerHelperText }}
            </p>
          </div>

          <!-- Model -->
          <UInput
            v-model="formModel"
            label="Model"
            placeholder="e.g. gpt-4o-mini, claude-3-haiku, llama3"
            help-text="Optional — Leave empty to use the provider default model."
          />

          <!-- Base URL -->
          <div v-if="showBaseUrlField">
            <label class="block text-sm font-medium text-theme-primary/70 mb-1">
              Base URL
              <span
                class="text-xs font-normal ml-1"
                :class="baseUrlConnected ? 'text-theme-primary' : baseUrlRequired ? 'text-danger' : 'text-theme-primary/50'"
              >
                ({{ baseUrlConnected ? 'Connected' : baseUrlRequired ? 'Required' : 'Optional' }})
              </span>
            </label>
            <input
              v-model="formBaseUrl"
              type="text"
              placeholder="e.g. http://localhost:11434/v1"
              class="focus-visible:outline-none focus-visible:border-theme-primary focus-visible:shadow-[0_0_0_2px_var(--color-theme-glow)] w-full rounded border-2 bg-surface-raised px-4 py-2 text-terminal-green transition-colors placeholder:text-theme-primary/40"
              :class="
                baseUrlConnected
                  ? 'border-theme-primary/60 focus:border-theme-primary'
                  : baseUrlRequired
                    ? 'border-danger/50 focus:border-danger'
                    : 'border-theme-primary/50 focus:border-theme-primary'
              "
            />
            <p
              class="mt-1 text-xs"
              :class="baseUrlConnected ? 'text-theme-primary' : baseUrlRequired ? 'text-danger/80' : 'text-theme-primary/50'"
            >
              {{
                baseUrlConnected
                  ? `Connection established — ${testResult?.model} responded via this endpoint.`
                  : baseUrlRequired
                    ? 'Required for Ollama / LM Studio — specify the local endpoint.'
                    : 'Leave empty to use the environment default.'
              }}
            </p>
          </div>

          <!-- Gateway Route -->
          <div class="opacity-80">
            <label class="block text-sm font-medium text-theme-primary/70 mb-1">
              Gateway Route
              <span class="text-xs text-theme-primary/50 font-normal ml-1">(Optional)</span>
            </label>
            <input
              v-model="formGatewayRoute"
              type="text"
              placeholder="e.g. anthropic, openai"
              class="focus-visible:outline-none focus-visible:border-theme-primary focus-visible:shadow-[0_0_0_2px_var(--color-theme-glow)] w-full rounded border-2 border-theme-primary/30 bg-surface-raised px-4 py-2 text-terminal-green transition-colors placeholder:text-theme-primary/40"
            />
            <p class="mt-1 text-xs text-theme-primary/50">
              Pydantic AI Gateway routing group — leave empty to use the env route.
            </p>
          </div>
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
            variant="secondary"
            :disabled="isLoading"
            :loading="isLoadingTest"
            @click="handleTest"
          >
            <Icon icon="mdi:connection" class="mr-1" />
            Test Connection
          </UButton>
          <UButton
            :variant="resetArmed ? 'danger' : 'secondary'"
            :disabled="isLoading"
            @click="handleReset"
            class="focus-visible:outline-none focus-visible:border-dashed focus-visible:shadow-[0_0_8px_var(--color-theme-glow)]"
          >
            <Icon icon="mdi:restore" class="mr-1" />
            {{ resetArmed ? 'Confirm Reset?' : 'Reset to Env Defaults' }}
          </UButton>
          <span v-if="!hasChanges" class="text-xs text-theme-primary/40 italic">
            No unsaved changes
          </span>
        </div>

        <!-- Test Result -->
        <div v-if="testResult" class="mt-4 rounded border-2 p-3 font-mono text-sm" :class="testResult.status === 'ok' ? 'border-theme-primary/50 bg-theme-primary/5' : 'border-danger/50 bg-danger/5'">
          <div class="flex items-start gap-2">
            <Icon
              :icon="testResult.status === 'ok' ? 'mdi:check-circle' : 'mdi:alert'"
              class="mt-0.5 h-5 w-5 shrink-0"
              :class="testResult.status === 'ok' ? 'text-theme-primary' : 'text-danger'"
            />
            <div class="min-w-0 flex-1">
              <div v-if="testResult.status === 'ok'" class="text-theme-primary">
                Connected in {{ testResult.latency_ms }} ms — model: {{ testResult.model }}
              </div>
              <div v-else class="text-danger">
                {{ testResult.message }}
                <span v-if="testResult.latency_ms" class="text-theme-primary/60 ml-2">
                  ({{ testResult.latency_ms }} ms)
                </span>
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Effective Config Panel -->
      <UCard glow crt>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <Icon icon="mdi:information-outline" class="h-6 w-6 text-theme-accent" />
              <h3 class="text-xl font-bold terminal-glow text-theme-primary">
                Effective Configuration
              </h3>
            </div>
            <button
              class="focus-visible:outline-none focus-visible:border-dashed focus-visible:border-theme-primary focus-visible:shadow-[0_0_8px_var(--color-theme-glow)] rounded border border-theme-primary/30 bg-transparent px-2 py-1 text-xs text-theme-primary/70 transition-colors hover:border-theme-primary/60 hover:text-theme-primary"
              :disabled="copiedConfig"
              @click="handleCopyConfig"
              aria-label="Copy configuration"
            >
              <Icon
                :icon="copiedConfig ? 'mdi:check' : 'mdi:content-copy'"
                class="mr-1 inline h-3.5 w-3.5"
              />
              {{ copiedConfig ? 'Copied' : 'Copy' }}
            </button>
          </div>
        </template>

        <div class="space-y-3 text-sm font-mono">
          <div class="flex justify-between items-baseline gap-4 min-w-0">
            <span class="text-theme-primary/60 uppercase text-[0.7rem] tracking-[0.05em] flex-shrink-0">Provider</span>
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span class="text-theme-primary text-right break-all min-w-0">{{ settings.effective.provider }}</span>
              <span
                v-if="getProvenance('provider') === 'profile'"
                class="override-pill rounded border border-theme-accent/50 bg-theme-accent/10 px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wider text-theme-accent"
              >
                Override
              </span>
            </div>
          </div>
          <div class="flex justify-between items-baseline gap-4 min-w-0">
            <span class="text-theme-primary/60 uppercase text-[0.7rem] tracking-[0.05em] flex-shrink-0">Model</span>
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span class="text-theme-primary text-right break-all min-w-0">{{ settings.effective.model }}</span>
              <span
                v-if="getProvenance('model') === 'profile'"
                class="override-pill rounded border border-theme-accent/50 bg-theme-accent/10 px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wider text-theme-accent"
              >
                Override
              </span>
            </div>
          </div>
          <div class="flex justify-between items-baseline gap-4 min-w-0">
            <span class="text-theme-primary/60 uppercase text-[0.7rem] tracking-[0.05em] flex-shrink-0">Base URL</span>
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span class="text-theme-primary text-right break-all min-w-0">{{ settings.effective.base_url || '—' }}</span>
              <span
                v-if="settings.effective.base_url && getProvenance('base_url') === 'profile'"
                class="override-pill rounded border border-theme-accent/50 bg-theme-accent/10 px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wider text-theme-accent"
              >
                Override
              </span>
            </div>
          </div>
          <div class="flex justify-between items-baseline gap-4 min-w-0">
            <span class="text-theme-primary/60 uppercase text-[0.7rem] tracking-[0.05em] flex-shrink-0">Gateway Route</span>
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span class="text-theme-primary text-right break-all min-w-0">{{ settings.effective.gateway_route || '—' }}</span>
              <span
                v-if="settings.effective.gateway_route && getProvenance('gateway_route') === 'profile'"
                class="override-pill rounded border border-theme-accent/50 bg-theme-accent/10 px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wider text-theme-accent"
              >
                Override
              </span>
            </div>
          </div>
          <div class="flex justify-between items-baseline gap-4 min-w-0">
            <span class="text-theme-primary/60 uppercase text-[0.7rem] tracking-[0.05em] flex-shrink-0">Mode</span>
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
              <span
                class="text-theme-primary text-right break-all min-w-0"
                :class="{
                  'text-terminal-green': settings.effective.mode !== 'disabled',
                  'text-red-400': settings.effective.mode === 'disabled',
                }"
              >
                {{ settings.effective.mode }}
              </span>
            </div>
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
/* Focus-visible rings for child-component internals (UButton/UInput/USelect).
   These `:deep` rules cannot be expressed as Tailwind utility classes because
   the focusable element lives inside the library component's own template. */
:deep(button):focus-visible {
  outline: none;
  border-style: dashed;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

:deep(select):focus-visible {
  outline: none;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 0 2px var(--color-theme-glow);
}

:deep(input):focus-visible {
  outline: none;
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 0 2px var(--color-theme-glow);
}
</style>
