<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useObjectivesStore } from '../stores/objectives'
import { currentObjective, objectiveActionPath } from '../models/objective'

const route = useRoute()
const store = useObjectivesStore()
const auth = useAuthStore()
const vaultStore = useVaultStore()
const toast = useToast()
const { isCollapsed } = useSidePanel()
const vaultId = computed(() =>
  route.path.startsWith('/vault/') && typeof route.params.id === 'string' ? route.params.id : null
)
const objective = computed(() =>
  vaultId.value && (!store.objectivesVaultId || store.objectivesVaultId === vaultId.value)
    ? currentObjective(store.objectives)
    : undefined
)
const ready = computed(() => objective.value && objective.value.progress >= objective.value.total)
const readyCount = computed(
  () => store.objectives.filter((item) => !item.is_completed && item.progress >= item.total).length
)
const claiming = ref(false)
const error = ref('')

async function refresh() {
  if (vaultId.value) await store.fetchObjectives(vaultId.value)
}
watch(
  vaultId,
  () => {
    error.value = ''
    void refresh().catch((err) => {
      error.value = getErrorMessage(err)
    })
  },
  { immediate: true }
)
usePolling(refresh, { interval: 30_000, immediate: false })

async function claim() {
  const id = vaultId.value
  const step = objective.value
  if (!id || !step || claiming.value) return
  claiming.value = true
  error.value = ''
  try {
    await store.completeObjective(id, step.id)
    void refresh().catch((err) => {
      error.value = getErrorMessage(err)
    })
    toast.success(`${step.reward} claimed`)
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    claiming.value = false
  }
  if (auth.token)
    void vaultStore
      .refreshVault(id, auth.token)
      .catch(() => toast.warning('Reward status may need a refresh'))
}
</script>

<template>
  <section
    v-if="objective && vaultId"
    aria-label="Current objective"
    class="mx-4 my-4 flex flex-col gap-3 rounded-md border border-theme-primary/40 bg-surface p-4 font-mono text-theme-primary md:flex-row md:items-center"
    :class="isCollapsed ? 'md:ml-20' : 'md:ml-64'"
  >
    <Icon icon="mdi:target" class="size-6 shrink-0" />
    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <p class="text-xs uppercase tracking-widest text-theme-accent">
        {{ objective.category === 'starter' ? 'Vault guide' : 'Next objective' }} ·
        {{ ready ? 'Reward ready' : 'In progress' }}
      </p>
      <h2 class="text-sm font-bold">{{ objective.challenge }}</h2>
      <p v-if="objective.description" class="text-xs text-theme-primary/70">
        {{ objective.description }}
      </p>
      <!-- @vue-ignore -->
      <Progress
        :model-value="Math.min(100, (objective.progress / Math.max(1, objective.total)) * 100)"
        class="h-1"
        aria-label="Objective progress"
      />
      <p class="text-xs">
        {{ objective.progress }} / {{ objective.total }} · Reward: {{ objective.reward }}
      </p>
      <p v-if="error" role="alert" class="text-danger">{{ error }}</p>
    </div>
    <div class="flex shrink-0 flex-wrap gap-2">
      <Button v-if="ready" size="sm" :disabled="claiming" @click="claim">{{
        claiming ? 'Claiming…' : `Claim ${objective.reward}`
      }}</Button>
      <Button v-else as-child size="sm"
        ><RouterLink :to="objectiveActionPath(objective, vaultId)"
          >Continue objective</RouterLink
        ></Button
      >
      <Button as-child size="sm" variant="secondary"
        ><RouterLink :to="`/vault/${vaultId}/objectives`"
          >All objectives{{ readyCount ? ` · ${readyCount} ready` : '' }}</RouterLink
        ></Button
      >
    </div>
  </section>
  <p v-else-if="vaultId && error" role="alert" class="m-4 text-danger">
    Unable to load objectives: {{ error }}
  </p>
</template>
