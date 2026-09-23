<template>
  <div class="pregnancy-tracker">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-mono text-theme-primary">
        Pregnancies
      </h2>
      <div class="flex gap-2">
        <Badge v-if="dueCount > 0" variant="outline" class="animate-pulse bg-warning text-black border-warning">
          {{ dueCount }} Due!
        </Badge>
        <Button variant="default" size="sm" class="border-2 border-theme-primary hover:shadow-glow-md" :disabled="isLoading" @click="refreshPregnancies"> Refresh </Button>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="text-4xl animate-pulse">👶</div>
      <p class="mt-2 text-theme-primary">Loading pregnancies...</p>
    </div>

    <div v-else-if="error" class="text-center py-8">
      <Card class="gap-0 rounded-lg border-2 border-theme-primary/20 p-6 shadow-glow-md ring-0 crt-screen">
        <p class="text-red-400 mb-4">{{ error }}</p>
        <Button variant="outline" class="border-2 border-theme-primary bg-transparent" @click="retryFetch()">Retry</Button>
      </Card>
    </div>

    <div v-else-if="pregnancies.length === 0" class="text-center py-8 text-gray-400">
      <p>No active pregnancies in this vault.</p>
      <p class="text-sm mt-2">Assign partners to living quarters to start families!</p>
    </div>

    <div v-else class="space-y-2">
      <PregnancyCard
        v-for="pregnancy in sortedPregnancies"
        :key="pregnancy.id"
        :pregnancy="pregnancy"
        :mother="getDweller(pregnancy.mother_id)"
        :father="getDweller(pregnancy.father_id)"
        :isDelivering="deliveringId === pregnancy.id"
        @deliver="deliverBaby(pregnancy.id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { usePolling } from '@/core/composables/usePolling'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import PregnancyCard from './PregnancyCard.vue'

interface Props {
  vaultId: string
  autoRefresh?: boolean
  refreshInterval?: number // seconds
}

const { autoRefresh = true, refreshInterval = 30, vaultId } = defineProps<Props>()

const pregnancyStore = usePregnancyStore()
const { filter: dwellerStore } = useDwellerStore()
const authStore = useAuthStore()

const pregnancies = computed(() => pregnancyStore.activePregnancies)
const isLoading = computed(() => pregnancyStore.isLoading)
const deliveringId = ref<string | null>(null)
const error = ref<string | null>(null)

/** Number of pregnancies that are currently due for delivery. */
const dueCount = computed(() => {
  return pregnancies.value.filter((p) => p.is_due).length
})

/** Active pregnancies sorted with due ones first, then by progress. */
const sortedPregnancies = computed(() => {
  return [...pregnancies.value].sort((a, b) => {
    // Due pregnancies first
    if (a.is_due && !b.is_due) return -1
    if (!a.is_due && b.is_due) return 1
    // Then by progress
    return b.progress_percentage - a.progress_percentage
  })
})

/**
 * Resolve a dweller by id from the roster, preferring the full dweller list
 * and falling back to the filtered list. Returns undefined when the dweller
 * has not been loaded yet.
 */
function getDweller(dwellerId: string): DwellerShort | undefined {
  return (
    dwellerStore.allDwellers.find((d) => d.id === dwellerId) ??
    dwellerStore.dwellers.find((d) => d.id === dwellerId)
  )
}

/** Reload the vault's pregnancies, capturing any failure into `error`. */
async function refreshPregnancies() {
  error.value = null
  try {
    await pregnancyStore.fetchVaultPregnancies(vaultId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load pregnancies'
  }
}

/** Re-run the initial pregnancy load after an error. */
function retryFetch() {
  refreshPregnancies()
}

/** Deliver a baby, refreshing the dweller roster so the newborn appears. */
async function deliverBaby(pregnancyId: string) {
  deliveringId.value = pregnancyId
  try {
    const result = await pregnancyStore.deliverBaby(pregnancyId)
    if (result) {
      // Refresh dwellers to show new baby
      await dwellerStore.fetchDwellersByVault(vaultId, authStore.token!)
    }
  } finally {
    deliveringId.value = null
  }
}

// Keep the refresh tied to this component's scope. Disabled auto-refresh
// retains the initial load without leaving an inactive browser timer behind.
const { pause: pausePolling } = usePolling(refreshPregnancies, {
  interval: refreshInterval * 1000,
  immediate: false,
})

if (!autoRefresh) pausePolling()

onMounted(() => {
  refreshPregnancies()
})
</script>
