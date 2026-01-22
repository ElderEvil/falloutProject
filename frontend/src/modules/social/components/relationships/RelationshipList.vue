<template>
  <div class="relationship-list">
    <div class="flex items-center justify-between mb-4">
      <h2 v-if="!stageFilter" class="text-xl font-mono" :style="{ color: 'var(--color-theme-primary)' }">Relationships</h2>
      <UButton @click="refreshRelationships" :disabled="isLoading" size="sm">
        <Icon icon="mdi:refresh" class="mr-1" />
        Refresh
      </UButton>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="text-4xl animate-pulse">💕</div>
      <p class="mt-2" :style="{ color: 'var(--color-theme-primary)' }">Loading relationships...</p>
    </div>

    <div v-else-if="filteredRelationships.length === 0" class="empty-state">
      <Icon icon="mdi:heart-outline" class="empty-icon" />
      <p class="empty-text">{{ emptyMessage }}</p>
      <p class="empty-hint">{{ emptyHint }}</p>
    </div>

    <div v-else class="space-y-2">
      <RelationshipCard
        v-for="relationship in filteredRelationships"
        :key="relationship.id"
        :relationship="relationship"
        :dweller1Name="getDwellerName(relationship.dweller_1_id)"
        :dweller2Name="getDwellerName(relationship.dweller_2_id)"
        @initiate-romance="initiateRomance(relationship.id)"
        @make-partners="makePartners(relationship.id)"
        @break-up="breakUp(relationship.id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useRelationshipStore } from '../../stores/relationship'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import RelationshipCard from './RelationshipCard.vue'
import UButton from '@/core/components/ui/UButton.vue'

interface Props {
  vaultId: string
  stageFilter?: 'forming' | 'partners'
}

const props = defineProps<Props>()

const relationshipStore = useRelationshipStore()
const dwellerStore = useDwellerStore()

const relationships = computed(() => relationshipStore.relationships)
const isLoading = computed(() => relationshipStore.isLoading)

const filteredRelationships = computed(() => {
  let filtered = [...relationships.value]

  // Apply stage filter
  if (props.stageFilter === 'forming') {
    filtered = filtered.filter(r => r.relationship_type !== 'partner')
  } else if (props.stageFilter === 'partners') {
    filtered = filtered.filter(r => r.relationship_type === 'partner')
  }

  // Sort by relationship type priority
  return filtered.sort((a, b) => {
    const priority: Record<string, number> = {
      partner: 0,
      romantic: 1,
      friend: 2,
      acquaintance: 3,
      ex: 4,
    }
    return (priority[a.relationship_type] ?? 5) - (priority[b.relationship_type] ?? 5)
  })
})

const emptyMessage = computed(() => {
  if (props.stageFilter === 'forming') {
    return 'No developing relationships in this vault yet.'
  } else if (props.stageFilter === 'partners') {
    return 'No partner couples in this vault yet.'
  }
  return 'No relationships in this vault yet.'
})

const emptyHint = computed(() => {
  if (props.stageFilter === 'forming') {
    return 'Assign dwellers to the same room to start building relationships!'
  } else if (props.stageFilter === 'partners') {
    return 'Relationships need to reach romantic status (70+ affinity) before becoming partners.'
  }
  return 'Assign dwellers to rooms together to start relationships!'
})

function getDwellerName(dwellerId: string): string {
  const dweller = dwellerStore.dwellers.find((d) => d.id === dwellerId)
  return dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Unknown'
}

async function refreshRelationships() {
  await relationshipStore.fetchVaultRelationships(props.vaultId)
}

async function initiateRomance(relationshipId: string) {
  await relationshipStore.initiateRomance(relationshipId)
}

async function makePartners(relationshipId: string) {
  await relationshipStore.makePartners(relationshipId)
}

async function breakUp(relationshipId: string) {
  if (confirm('Are you sure you want to end this relationship?')) {
    await relationshipStore.breakUp(relationshipId)
  }
}

onMounted(() => {
  refreshRelationships()
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 4rem;
  color: var(--color-theme-primary);
  opacity: 0.3;
  margin-bottom: 1rem;
}

.empty-text {
  font-size: 1.125rem;
  color: var(--color-theme-primary);
  margin-bottom: 0.5rem;
}

.empty-hint {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
}
</style>
