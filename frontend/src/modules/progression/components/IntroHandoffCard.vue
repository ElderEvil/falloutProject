<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Alert } from '@/core/components/ui/alert'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import {
  getDwellerDisplayName,
  isAvailableUnassignedDweller,
  isMature,
} from '@/modules/dwellers/models/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useExplorationProgress } from '@/modules/exploration/composables/useExplorationProgress'
import type { Objective } from '../models/objective'
import {
  isObjectiveClaimable,
  objectiveActionPath,
  objectiveDescription,
  objectiveRewardDetails,
} from '../models/objective'
import { storageService } from '@/modules/storage/services/storageService'
import { useVaultStore } from '@/modules/vault/stores/vault'

const props = defineProps<{
  vaultId: string
  compact?: boolean
  readyCount?: number
  milestone?: Objective
  claiming?: boolean
  claimError?: string | null
}>()
const emit = defineEmits<{ dismiss: []; claim: []; hide: [] }>()
const router = useRouter()
const auth = useAuthStore()
const dwellers = useDwellerStore()
const explorations = useExplorationStore()
const vaults = useVaultStore()
const context = ref<{ vaultId: string; unassignedName?: string; hasEquipment: boolean } | null>(
  null
)
const loading = ref(false)
const error = ref<string | null>(null)
let generation = 0

// Reuse the guide's existing refresh cadence; this card owns no polling timer.
async function refresh(): Promise<void> {
  if (props.compact || loading.value) return
  const vaultId = props.vaultId
  const token = auth.token
  if (!token) return
  const request = ++generation
  loading.value = true
  error.value = null
  try {
    const [, , items] = await Promise.all([
      explorations.fetchExplorationsByVault(vaultId),
      dwellers.filter.fetchAllDwellers(vaultId, true),
      storageService.getStorageItems(vaultId),
    ])
    if (request !== generation || props.vaultId !== vaultId) return
    const unassigned = dwellers.filter.allDwellers.find(
      (dweller) => isAvailableUnassignedDweller(dweller) && isMature(dweller) && dweller.health > 0
    )
    context.value = {
      vaultId,
      unassignedName: unassigned ? getDwellerDisplayName(unassigned) : undefined,
      hasEquipment: [...items.weapons, ...items.outfits].some((item) => !item.dweller_id),
    }
  } catch (err) {
    if (request !== generation || props.vaultId !== vaultId) return
    error.value = getErrorMessage(err)
    handleStoreError(err, 'Failed to refresh the introductory handoff', false)
  } finally {
    if (request === generation) loading.value = false
  }
}

watch(
  () => props.vaultId,
  () => {
    ++generation
    context.value = null
    loading.value = false
    void refresh()
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  ++generation
})
defineExpose({ refresh })

const run = computed(() => explorations.getActiveExplorationsForVault(props.vaultId)[0])
const { timeRemaining } = useExplorationProgress(run)
const suggestion = computed(() => {
  if (context.value?.vaultId !== props.vaultId) return null
  const vaultPath = `/vault/${props.vaultId}`
  const warning = vaults.loadedVaults[props.vaultId]?.resource_warnings?.[0]
  if (warning)
    return {
      body: `${warning.message} Review production before sending anyone else out.`,
      label: 'Review production',
      path: vaultPath,
    }
  if (context.value.unassignedName)
    return {
      body: `${context.value.unassignedName} is available for a job. Review their SPECIAL and an open room slot.`,
      label: 'Review assignment',
      path: `${vaultPath}/dwellers`,
    }
  if (context.value.hasEquipment)
    return {
      body: 'There is equipment in storage. Review it for a useful upgrade before the next expedition.',
      label: 'Review equipment',
      path: `${vaultPath}/storage`,
    }
  return {
    body: 'Nothing else is required by this guide. Check the Briefing for current priorities, or come back later.',
    label: 'Open Vault',
    path: vaultPath,
  }
})
const milestoneReward = computed(() => objectiveRewardDetails(props.milestone?.reward ?? ''))
const milestoneAction = computed(() => {
  switch (props.milestone?.objective_type) {
    case 'expedition':
      return 'Choose mission'
    case 'train':
      return 'Open training'
    case 'build':
    case 'collect':
      return 'Manage vault'
    case 'reach':
      return 'Review crew'
    default:
      return 'Open task'
  }
})
</script>

<template>
  <Card v-if="compact" v-bind="{ role: 'region', 'aria-label': 'Vault guide' }">
    <CardHeader class="gap-1 p-0">
      <p class="text-xs font-bold tracking-widest text-theme-accent">VAULT GUIDE</p>
      <CardTitle class="text-base"
        ><h2>{{ milestone?.challenge ?? 'Your next milestone' }}</h2></CardTitle
      >
      <CardDescription v-if="milestone">{{ objectiveDescription(milestone) }}</CardDescription>
    </CardHeader>
    <CardContent v-if="milestone" class="space-y-2 p-0">
      <p class="text-xs font-bold">{{ milestone.progress }} / {{ milestone.total }}</p>
      <p class="text-sm">
        Reward:
        {{
          milestoneReward.kind === 'dweller'
            ? `${milestoneReward.name} joins your vault`
            : milestoneReward.name
        }}
      </p>
      <Alert v-if="claimError" variant="destructive">{{ claimError }}</Alert>
    </CardContent>
    <CardFooter class="flex-wrap gap-2 p-0">
      <template v-if="milestone">
        <Button
          v-if="isObjectiveClaimable(milestone)"
          size="sm"
          :disabled="claiming"
          @click="emit('claim')"
          >{{ claiming ? 'Claiming…' : `Claim ${milestoneReward.name}` }}</Button
        >
        <Button
          size="sm"
          variant="outline"
          :disabled="claiming"
          @click="router.push(objectiveActionPath(milestone, vaultId))"
          >{{ milestoneAction }}</Button
        >
      </template>
      <Button
        size="sm"
        variant="outline"
        :disabled="claiming"
        @click="router.push(`/vault/${vaultId}/objectives`)"
        >{{ readyCount ? `View ${readyCount} ready rewards` : 'View milestones' }}</Button
      >
      <Button size="sm" variant="ghost" :disabled="claiming" @click="emit('hide')"
        >Hide guide</Button
      >
    </CardFooter>
  </Card>
  <Card v-else v-bind="{ role: 'region', 'aria-label': 'First expedition handoff' }">
    <CardHeader class="gap-1 p-0">
      <CardTitle class="text-base">{{
        run ? 'While they’re away' : 'You know the basics'
      }}</CardTitle>
      <CardDescription
        >The introductory tour is complete. Finish it to continue with optional vault
        milestones.</CardDescription
      >
    </CardHeader>
    <CardContent class="flex flex-col gap-3 p-0">
      <p v-if="!context && !error" role="status" class="text-sm text-muted-foreground">
        Checking your vault…
      </p>
      <Alert v-else-if="error" variant="destructive">
        Could not refresh your vault. {{ error }}
        <Button size="sm" variant="outline" :disabled="loading" @click="refresh">Retry</Button>
      </Alert>
      <template v-else-if="suggestion">
        <p class="text-sm">
          <template v-if="run"
            >{{
              run.status === 'returning'
                ? 'Your explorer is heading home.'
                : 'Your explorer is in the wasteland.'
            }}
            {{ timeRemaining }}</template
          >
          <template v-else
            >No explorers are currently away. Check Exploration for returns and reports.</template
          >
        </p>
        <Button
          size="sm"
          variant="outline"
          @click="router.push(`/vault/${vaultId}/exploration${run ? `/${run.id}` : ''}`)"
        >
          {{ run ? 'View expedition' : 'Open Exploration' }}
        </Button>
        <p class="text-sm text-muted-foreground">{{ suggestion.body }}</p>
        <Button size="sm" variant="outline" @click="router.push(suggestion.path)">{{
          suggestion.label
        }}</Button>
      </template>
    </CardContent>
    <CardFooter class="p-0">
      <Button size="sm" variant="ghost" @click="emit('dismiss')">Finish intro</Button>
    </CardFooter>
  </Card>
</template>
