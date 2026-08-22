<template>
  <div class="relationship-list">
    <div class="flex items-center justify-between mb-4">
      <h2
        v-if="!stageFilter"
        class="text-xl font-mono"
        :style="{ color: 'var(--color-theme-primary)' }"
      >
        Relationships
      </h2>
      <div class="flex items-center gap-2">
        <div class="flex rounded border border-theme-primary/20 p-0.5">
          <UButton variant="ghost" size="xs" :class="viewMode === 'list' ? 'bg-theme-glow/20!' : ''" title="List view" @click="viewMode = 'list'">
            <Icon icon="mdi:format-list-bulleted" />
          </UButton>
          <UButton variant="ghost" size="xs" :class="viewMode === 'grid' ? 'bg-theme-glow/20!' : ''" title="Grid view" @click="viewMode = 'grid'">
            <Icon icon="mdi:view-grid-outline" />
          </UButton>
        </div>
        <UButton @click="refreshRelationships" :disabled="isLoading" size="sm">
          <Icon icon="mdi:refresh" class="mr-1" />
          Refresh
        </UButton>
      </div>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="text-4xl animate-pulse">💕</div>
      <p class="mt-2" :style="{ color: 'var(--color-theme-primary)' }">Loading relationships...</p>
    </div>

    <div v-else-if="error" class="error-state text-center py-8">
      <UCard glow crt class="p-6">
        <p class="text-red-400 mb-4">{{ error }}</p>
        <UButton variant="danger" @click="retryFetch()">Retry</UButton>
      </UCard>
    </div>

    <TerminalEmptyState
      v-else-if="filteredRelationships.length === 0"
      icon="mdi:heart-outline"
      :title="emptyMessage"
      :description="emptyHint"
    />

    <div v-else :class="viewMode === 'grid' ? 'grid grid-cols-1 gap-4 xl:grid-cols-2' : 'space-y-2'">
      <div
        v-for="relationship in filteredRelationships"
        :key="relationship.id"
        class="relationship-entry"
      >
        <RelationshipCard
          :relationship="relationship"
          :dweller1Name="getDwellerName(relationship.dweller_1_id)"
          :dweller2Name="getDwellerName(relationship.dweller_2_id)"
          :view-mode="viewMode"
          @select-dweller="emit('select-dweller', $event)"
          @initiate-romance="initiateRomance(relationship.id)"
          @make-partners="makePartners(relationship.id)"
          @marry="marry(relationship.id)"
          @break-up="breakUp(relationship.id)"
        />
        <CoupleFamilyDiagram
          v-if="
            isPartnerLinked(relationship) &&
            getDweller(relationship.dweller_1_id) &&
            getDweller(relationship.dweller_2_id)
          "
          :dweller1="getDweller(relationship.dweller_1_id)!"
          :dweller2="getDweller(relationship.dweller_2_id)!"
          @select="emit('select-dweller', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useRelationshipStore } from '../../stores/relationship'
import {
  isRelationshipType,
  PARTNER_LINKED_RELATIONSHIP_TYPES,
  type Relationship,
  type RelationshipType,
} from '../../models/relationship'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RelationshipCard from './RelationshipCard.vue'
import CoupleFamilyDiagram from './CoupleFamilyDiagram.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UCard from '@/core/components/ui/UCard.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'

interface Props {
  vaultId: string
  stageFilter?: 'forming' | 'partners'
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'select-dweller', dwellerId: string): void }>()

const relationshipStore = useRelationshipStore()
const { filter: dwellerStore } = useDwellerStore()

const relationships = computed(() => relationshipStore.relationships)
const isLoading = computed(() => relationshipStore.isLoading)
const error = ref<string | null>(null)
const viewMode = ref<'list' | 'grid'>('list')

const filteredRelationships = computed(() => {
  let filtered = [...relationships.value]

  // Apply stage filter
  if (props.stageFilter === 'forming') {
    filtered = filtered.filter(
      (r) => !isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    )
  } else if (props.stageFilter === 'partners') {
    filtered = filtered.filter((r) =>
      isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    )
  }

  // Sort by relationship type priority
  return filtered.sort((a, b) => {
    const priority: Record<RelationshipType, number> = {
      partner: 0,
      MARRIED: 0,
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

function getDweller(dwellerId: string): DwellerShort | undefined {
  return dwellerStore.dwellers.find((d) => d.id === dwellerId)
}

function isPartnerLinked(relationship: Relationship): boolean {
  return isRelationshipType(relationship.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
}

async function refreshRelationships() {
  error.value = null
  try {
    await relationshipStore.fetchVaultRelationships(props.vaultId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load relationships'
  }
}

function retryFetch() {
  refreshRelationships()
}

async function initiateRomance(relationshipId: string) {
  await relationshipStore.initiateRomance(relationshipId)
}

async function makePartners(relationshipId: string) {
  await relationshipStore.makePartners(relationshipId)
}

async function marry(relationshipId: string) {
  await relationshipStore.marry(relationshipId)
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
