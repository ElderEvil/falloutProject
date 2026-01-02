<template>
  <UCard class="mb-2">
    <div class="flex items-center justify-between gap-4">
      <!-- Dweller names -->
      <div class="flex-1">
        <div class="flex items-center gap-2">
          <span class="font-mono">{{ dweller1Name }}</span>
          <span class="text-green-400">♥</span>
          <span class="font-mono">{{ dweller2Name }}</span>
        </div>

        <!-- Relationship type badge -->
        <UBadge :color="relationshipColor" class="mt-1">
          {{ relationship.relationship_type }}
        </UBadge>
      </div>

      <!-- Affinity bar -->
      <div class="w-32">
        <div class="text-xs text-green-400 mb-1">Affinity: {{ relationship.affinity }}/100</div>
        <div class="h-2 bg-gray-800 border border-green-600">
          <div
            class="h-full bg-green-500"
            :style="{ width: `${relationship.affinity}%` }"
          ></div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-2">
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
          v-if="relationship.relationship_type === 'romantic' || relationship.relationship_type === 'partner'"
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
import type { Relationship } from '@/models/relationship'
import UCard from '@/components/ui/UCard.vue'
import UBadge from '@/components/ui/UBadge.vue'
import UButton from '@/components/ui/UButton.vue'

interface Props {
  relationship: Relationship
  dweller1Name: string
  dweller2Name: string
}

const props = defineProps<Props>()

defineEmits<{
  'initiate-romance': []
  'make-partners': []
  'break-up': []
}>()

const relationshipColor = computed(() => {
  switch (props.relationship.relationship_type) {
    case 'partner':
      return 'red'
    case 'romantic':
      return 'pink'
    case 'friend':
      return 'yellow'
    case 'ex':
      return 'gray'
    default:
      return 'green'
  }
})
</script>
