<template>
  <UCard v-if="props.viewMode === 'grid'" padding="md" class="relationship-card relationship-record--grid h-full">
    <div class="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_12rem_auto]">
      <div class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
        <button
          type="button"
          :title="`View ${dweller1Name}`"
          class="group min-w-0 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_1_id)"
        >
          <span class="block text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary/55">DWELLER 01</span>
          <span class="mt-1 block truncate text-sm font-bold text-theme-primary group-hover:underline">{{ dweller1Name }}</span>
        </button>
        <div class="flex flex-col items-center gap-1 text-theme-primary/70">
          <Icon icon="mdi:heart" class="h-5 w-5 [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]" />
          <UBadge :variant="relationshipColor" class="relationship-badge mt-1 text-[0.625rem]">
            {{ relationship.relationship_type }}
          </UBadge>
        </div>
        <button
          type="button"
          :title="`View ${dweller2Name}`"
          class="group min-w-0 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-right transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
          @click="emit('select-dweller', relationship.dweller_2_id)"
        >
          <span class="block text-[0.65rem] font-bold tracking-[0.12em] text-theme-primary/55">DWELLER 02</span>
          <span class="mt-1 block truncate text-sm font-bold text-theme-primary group-hover:underline">{{ dweller2Name }}</span>
        </button>
      </div>

      <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="font-bold tracking-[0.08em] text-theme-primary/60">AFFINITY</span>
          <span class="font-bold text-theme-primary">{{ relationship.affinity }}/100</span>
        </div>
        <UProgressBar :model-value="relationship.affinity" :height="8" class="mt-2" />
        <p v-if="nextMilestone" class="mt-2 text-xs leading-4 text-theme-primary/60">
          {{ nextMilestone }}
        </p>
      </div>

      <div class="flex flex-wrap justify-end gap-2">
        <UButton
          v-if="relationship.relationship_type === 'acquaintance' && relationship.affinity >= 70"
          @click="$emit('initiate-romance')"
          size="sm"
        >
          Romance
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'romantic'"
          @click="$emit('make-partners')"
          size="sm"
        >
          Partner
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'partner' && relationship.affinity >= 85"
          @click="$emit('marry')"
          size="sm"
        >
          Marry
        </UButton>
        <UButton
          v-if="isRelationshipType(relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)"
          @click="$emit('break-up')"
          variant="danger"
          size="sm"
        >
          Break Up
        </UButton>
      </div>
    </div>
  </UCard>
  <UCard v-else padding="sm" class="relationship-record--list">
    <div class="grid items-center gap-3 md:grid-cols-[minmax(0,1fr)_10rem_auto]">
      <div class="min-w-0">
        <div class="flex min-w-0 items-center gap-2">
          <button
            type="button"
            :title="`View ${dweller1Name}`"
            class="truncate text-left font-bold text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
            @click="emit('select-dweller', relationship.dweller_1_id)"
          >
            {{ dweller1Name }}
          </button>
          <Icon icon="mdi:heart" class="h-4 w-4 shrink-0 text-theme-primary/70" />
          <button
            type="button"
            :title="`View ${dweller2Name}`"
            class="truncate text-left font-bold text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
            @click="emit('select-dweller', relationship.dweller_2_id)"
          >
            {{ dweller2Name }}
          </button>
        </div>
        <UBadge :variant="relationshipColor" class="relationship-badge mt-1 text-[0.625rem]">
          {{ relationship.relationship_type }}
        </UBadge>
      </div>
      <div class="rounded border border-theme-primary/15 bg-surface-sunken px-2.5 py-2">
        <div class="flex items-center justify-between text-xs text-theme-primary/70">
          <span>AFFINITY</span>
          <span class="font-bold text-theme-primary">{{ relationship.affinity }}/100</span>
        </div>
        <UProgressBar :model-value="relationship.affinity" :height="6" class="mt-1.5" />
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        <UButton
          v-if="relationship.relationship_type === 'acquaintance' && relationship.affinity >= 70"
          @click="emit('initiate-romance')"
          size="sm"
        >
          Romance
        </UButton>
        <UButton v-if="relationship.relationship_type === 'romantic'" @click="emit('make-partners')" size="sm">
          Partner
        </UButton>
        <UButton
          v-if="relationship.relationship_type === 'partner' && relationship.affinity >= 85"
          @click="emit('marry')"
          size="sm"
        >
          Marry
        </UButton>
        <UButton
          v-if="isRelationshipType(relationship.relationship_type, COMMITTED_RELATIONSHIP_TYPES)"
          @click="emit('break-up')"
          variant="danger"
          size="sm"
        >
          Break Up
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  COMMITTED_RELATIONSHIP_TYPES,
  isRelationshipType,
  RELATIONSHIP_TYPE_VARIANT,
  type Relationship,
} from '../../models/relationship'
import { useRelationshipMilestone } from '../../composables/useRelationshipMilestone'
import UCard from '@/core/components/ui/UCard.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'

interface Props {
  relationship: Relationship
  dweller1Name: string
  dweller2Name: string
  viewMode?: 'list' | 'grid'
}

const props = withDefaults(defineProps<Props>(), { viewMode: 'list' })

const emit = defineEmits<{
  'initiate-romance': []
  'make-partners': []
  marry: []
  'break-up': []
  'select-dweller': [dwellerId: string]
}>()

const relationshipColor = computed(
  () => RELATIONSHIP_TYPE_VARIANT[props.relationship.relationship_type] ?? 'success'
)

const { nextMilestone } = useRelationshipMilestone(() => props.relationship)
</script>
