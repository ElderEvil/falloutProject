<template>
  <div class="relationship-list">
    <div class="flex items-center justify-between mb-4">
      <h2
        v-if="!stageFilter"
        class="text-xl font-mono text-theme-primary"
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
      <p class="mt-2 text-theme-primary">Loading relationships...</p>
    </div>

    <div v-else-if="error" class="error-state text-center py-8">
      <UCard glow crt class="p-6">
        <p class="text-red-400 mb-4">{{ error }}</p>
        <UButton variant="secondary" @click="retryFetch()">Retry</UButton>
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
        v-for="entry in resolvedRelationships"
        :key="entry.relationship.id"
        class="relationship-entry"
      >
        <RelationshipCard
          :relationship="entry.relationship"
          :dweller1="entry.dweller1"
          :dweller2="entry.dweller2"
          :children="getChildren(entry.relationship)"
          :pregnancy="getPregnancy(entry.relationship)"
          :generation="getGeneration(entry.relationship)"
          :view-mode="viewMode"
          @select-dweller="emit('select-dweller', $event)"
          @initiate-romance="initiateRomance(entry.relationship.id)"
          @make-partners="makePartners(entry.relationship.id)"
          @marry="marry(entry.relationship.id)"
          @break-up="breakUp(entry.relationship.id)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useRelationshipStore } from '../../stores/relationship'
import { usePregnancyStore } from '../../stores/pregnancy'
import {
  isRelationshipType,
  PARTNER_LINKED_RELATIONSHIP_TYPES,
  type Relationship,
  type RelationshipType,
} from '../../models/relationship'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RelationshipCard from './RelationshipCard.vue'
import { childrenOfCouple, generationOf } from '../../models/dwellerFamily'
import { pregnancyForCouple } from '../../models/pregnancy'
import type { Pregnancy } from '../../models/pregnancy'
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
const pregnancyStore = usePregnancyStore()
const { filter: dwellerStore } = useDwellerStore()

const relationships = computed(() => relationshipStore.relationships)
const isLoading = computed(() => relationshipStore.isLoading)
const error = ref<string | null>(null)
const viewMode = ref<'list' | 'grid'>('list')

/** A relationship paired with its two resolved dweller records. */
interface ResolvedRelationship {
  relationship: Relationship
  dweller1: DwellerShort
  dweller2: DwellerShort
}

/**
 * Filtered relationships whose both dwellers are present in the roster.
 * Relationships whose dwellers have not loaded yet are omitted until the
 * roster arrives (the view fetches all dwellers on mount).
 */
const resolvedRelationships = computed<ResolvedRelationship[]>(() =>
  filteredRelationships.value.flatMap((relationship) => {
    const dweller1 = getDweller(relationship.dweller_1_id)
    const dweller2 = getDweller(relationship.dweller_2_id)
    return dweller1 && dweller2 ? [{ relationship, dweller1, dweller2 }] : []
  })
)

/** Relationships filtered by stage and sorted by relationship type priority. */
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

/** Empty-state title for the current stage filter. */
const emptyMessage = computed(() => {
  if (props.stageFilter === 'forming') {
    return 'No developing relationships in this vault yet.'
  } else if (props.stageFilter === 'partners') {
    return 'No partner couples in this vault yet.'
  }
  return 'No relationships in this vault yet.'
})

/** Empty-state hint for the current stage filter. */
const emptyHint = computed(() => {
  if (props.stageFilter === 'forming') {
    return 'Assign dwellers to the same room to start building relationships!'
  } else if (props.stageFilter === 'partners') {
    return 'Relationships need to reach romantic status (70+ affinity) before becoming partners.'
  }
  return 'Assign dwellers to rooms together to start relationships!'
})

/**
 * Resolve a dweller by id from the roster, preferring the filtered list and
 * falling back to the full dweller list. Returns undefined when the dweller
 * has not been loaded yet.
 */
function getDweller(dwellerId: string): DwellerShort | undefined {
  return (
    dwellerStore.dwellers.find((d) => d.id === dwellerId) ??
    dwellerStore.allDwellers.find((d) => d.id === dwellerId)
  )
}

/** Children shared by both members of the relationship. */
function getChildren(relationship: Relationship): DwellerShort[] {
  return childrenOfCouple(
    dwellerStore.allDwellers,
    relationship.dweller_1_id,
    relationship.dweller_2_id
  )
}

/** Active pregnancy for the couple, or null when none is in progress. */
function getPregnancy(relationship: Relationship): Pregnancy | null {
  return pregnancyForCouple(
    pregnancyStore.pregnancies,
    relationship.dweller_1_id,
    relationship.dweller_2_id
  )
}

/** Highest in-vault generation among the two relationship members. */
function getGeneration(relationship: Relationship): number {
  return Math.max(
    generationOf(dwellerStore.allDwellers, relationship.dweller_1_id),
    generationOf(dwellerStore.allDwellers, relationship.dweller_2_id)
  )
}

/** Whether the relationship type counts as a committed partner link. */
function isPartnerLinked(relationship: Relationship): boolean {
  return isRelationshipType(relationship.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
}

/** Reload the vault's relationships, capturing any failure into `error`. */
async function refreshRelationships() {
  error.value = null
  try {
    await relationshipStore.fetchVaultRelationships(props.vaultId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load relationships'
  }
}

/** Re-run the initial relationship load after an error. */
function retryFetch() {
  refreshRelationships()
}

/** Promote the relationship to a romantic one. */
async function initiateRomance(relationshipId: string) {
  await relationshipStore.initiateRomance(relationshipId)
}

/** Promote the relationship to a committed partner link. */
async function makePartners(relationshipId: string) {
  await relationshipStore.makePartners(relationshipId)
}

/** Marry the committed couple. */
async function marry(relationshipId: string) {
  await relationshipStore.marry(relationshipId)
}

/** End the relationship after a confirmation prompt. */
async function breakUp(relationshipId: string) {
  if (confirm('Are you sure you want to end this relationship?')) {
    await relationshipStore.breakUp(relationshipId)
  }
}

onMounted(() => {
  refreshRelationships()
})
</script>
