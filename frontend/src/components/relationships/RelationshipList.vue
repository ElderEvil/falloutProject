<template>
  <div class="relationship-list">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-mono text-green-400">Relationships</h2>
      <UButton @click="refreshRelationships" :disabled="isLoading">
        Refresh
      </UButton>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="text-4xl animate-pulse">💕</div>
      <p class="mt-2 text-green-400">Loading relationships...</p>
    </div>

    <div v-else-if="relationships.length === 0" class="text-center py-8 text-gray-400">
      <p>No relationships in this vault yet.</p>
      <p class="text-sm mt-2">Assign dwellers to living quarters to start relationships!</p>
    </div>

    <div v-else class="space-y-2">
      <RelationshipCard
        v-for="relationship in sortedRelationships"
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
import { useRelationshipStore } from '@/stores/relationship'
import { useDwellerStore } from '@/stores/dweller'
import RelationshipCard from './RelationshipCard.vue'
import UButton from '@/components/ui/UButton.vue'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()

const relationshipStore = useRelationshipStore()
const dwellerStore = useDwellerStore()

const relationships = computed(() => relationshipStore.relationships)
const isLoading = computed(() => relationshipStore.isLoading)

const sortedRelationships = computed(() => {
  return [...relationships.value].sort((a, b) => {
    // Sort by relationship type priority
    const priority: Record<string, number> = {
      partner: 0,
      romantic: 1,
      friend: 2,
      acquaintance: 3,
      ex: 4,
    }
    return priority[a.relationship_type] - priority[b.relationship_type]
  })
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
