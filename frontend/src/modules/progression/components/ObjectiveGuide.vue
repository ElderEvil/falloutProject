<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useObjectivesStore } from '../stores/objectives'
import { useObjectiveClaim } from '../composables/useObjectiveClaim'
import { currentObjective, objectiveActionPath } from '../models/objective'

const route = useRoute()
const store = useObjectivesStore()
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
const loadError = ref('')
const { claiming, error: claimError, claim } = useObjectiveClaim(vaultId)

async function refresh() {
  if (vaultId.value) await store.fetchObjectives(vaultId.value)
}
watch(
  vaultId,
  () => {
    loadError.value = ''
    void refresh().catch((err) => {
      loadError.value = getErrorMessage(err)
    })
  },
  { immediate: true }
)
usePolling(refresh, { interval: 30_000, immediate: false })

function claimCurrent() {
  const step = objective.value
  if (!step) return
  void claim(step.id, (claimed) => toast.success(`${claimed.reward} claimed`))
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
      <progress
        :value="objective.progress"
        :max="Math.max(1, objective.total)"
        class="h-1 w-full accent-theme-primary"
        aria-label="Objective progress"
      />
      <p class="text-xs">
        {{ objective.progress }} / {{ objective.total }} · Reward: {{ objective.reward }}
      </p>
      <p v-if="claimError" role="alert" class="text-danger">{{ claimError }}</p>
    </div>
    <div class="flex shrink-0 flex-wrap gap-2">
      <Button v-if="ready" size="sm" :disabled="claiming" @click="claimCurrent">{{
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
  <p v-else-if="vaultId && loadError" role="alert" class="m-4 text-danger">
    Unable to load objectives: {{ loadError }}
  </p>
</template>
