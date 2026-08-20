<template>
  <UCard class="mb-2">
    <div class="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_10rem_auto] items-center gap-4">
      <!-- Dweller names -->
      <div class="min-w-0">
        <div class="flex items-center gap-2 min-w-0">
          <span class="font-mono truncate">{{ dweller1Name }}</span>
          <span class="shrink-0" :style="{ color: 'var(--color-theme-primary)' }">♥</span>
          <span class="font-mono truncate">{{ dweller2Name }}</span>
        </div>

        <!-- Relationship type badge -->
        <UBadge :variant="relationshipColor" class="mt-1">
          {{ relationship.relationship_type }}
        </UBadge>
      </div>

      <!-- Affinity bar (fixed column position) -->
      <div class="w-full md:w-40">
        <div class="text-xs mb-1" :style="{ color: 'var(--color-theme-primary)' }">
          Affinity: {{ relationship.affinity }}/100
        </div>
        <UProgressBar :model-value="relationship.affinity" :height="10" />
        <div v-if="nextMilestone" class="text-xs mt-1 milestone-hint">
          {{ nextMilestone }}
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-2 justify-end">
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
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
}

const props = defineProps<Props>()

defineEmits<{
  'initiate-romance': []
  'make-partners': []
  marry: []
  'break-up': []
}>()

const relationshipColor = computed(
  () => RELATIONSHIP_TYPE_VARIANT[props.relationship.relationship_type] ?? 'success'
)

const { nextMilestone } = useRelationshipMilestone(() => props.relationship)
</script>

<style scoped>
.milestone-hint {
  color: var(--color-theme-primary);
  opacity: 0.6;
}
</style>
