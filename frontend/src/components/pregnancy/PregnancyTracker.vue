<template>
  <div class="pregnancy-tracker">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-mono" :style="{ color: 'var(--color-theme-primary)' }">Pregnancies</h2>
      <div class="flex gap-2">
        <UBadge v-if="dueCount > 0" color="yellow" class="animate-pulse">
          {{ dueCount }} Due!
        </UBadge>
        <UButton @click="refreshPregnancies" :disabled="isLoading" size="sm">
          Refresh
        </UButton>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="text-4xl animate-pulse">👶</div>
      <p class="mt-2" :style="{ color: 'var(--color-theme-primary)' }">Loading pregnancies...</p>
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
        :motherName="getDwellerName(pregnancy.mother_id)"
        :fatherName="getDwellerName(pregnancy.father_id)"
        :isDelivering="deliveringId === pregnancy.id"
        @deliver="deliverBaby(pregnancy.id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, onUnmounted } from 'vue'
import { usePregnancyStore } from '@/stores/pregnancy'
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import PregnancyCard from './PregnancyCard.vue'
import UButton from '@/components/ui/UButton.vue'
import UBadge from '@/components/ui/UBadge.vue'

interface Props {
  vaultId: string
  autoRefresh?: boolean
  refreshInterval?: number // seconds
}

const props = withDefaults(defineProps<Props>(), {
  autoRefresh: true,
  refreshInterval: 30,
})

const pregnancyStore = usePregnancyStore()
const dwellerStore = useDwellerStore()
const authStore = useAuthStore()

const pregnancies = computed(() => pregnancyStore.activePregnancies)
const isLoading = computed(() => pregnancyStore.isLoading)
const deliveringId = ref<string | null>(null)

const dueCount = computed(() => {
  return pregnancies.value.filter((p) => p.is_due).length
})

const sortedPregnancies = computed(() => {
  return [...pregnancies.value].sort((a, b) => {
    // Due pregnancies first
    if (a.is_due && !b.is_due) return -1
    if (!a.is_due && b.is_due) return 1
    // Then by progress
    return b.progress_percentage - a.progress_percentage
  })
})

function getDwellerName(dwellerId: string): string {
  const dweller = dwellerStore.dwellers.find((d) => d.id === dwellerId)
  return dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Unknown'
}

async function refreshPregnancies() {
  await pregnancyStore.fetchVaultPregnancies(props.vaultId)
}

async function deliverBaby(pregnancyId: string) {
  deliveringId.value = pregnancyId
  try {
    const result = await pregnancyStore.deliverBaby(pregnancyId)
    if (result) {
      // Refresh dwellers to show new baby
      await dwellerStore.fetchDwellersByVault(props.vaultId, authStore.token!)
    }
  } finally {
    deliveringId.value = null
  }
}

// Auto-refresh
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  refreshPregnancies()

  if (props.autoRefresh) {
    refreshTimer = setInterval(() => {
      refreshPregnancies()
    }, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>
