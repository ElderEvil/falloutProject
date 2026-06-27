<template>
  <UCard class="mb-2 bg-black/90">
    <div class="flex items-center justify-between gap-4">
      <!-- Dweller names -->
      <div class="flex-1">
        <div class="flex items-center gap-2">
          <span class="font-mono">{{ dweller1Name }}</span>
          <span :style="{ color: 'var(--color-theme-primary)' }">♥</span>
          <span class="font-mono">{{ dweller2Name }}</span>
        </div>

        <!-- Relationship type badge -->
        <span
          class="mt-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
          :class="badgeClass"
        >
          {{ relationship.relationship_type }}
        </span>
      </div>

      <!-- Affinity bar -->
      <div class="w-32">
        <div class="text-xs mb-1" :style="{ color: 'var(--color-theme-primary)' }">
          Affinity: {{ relationship.affinity }}/100
        </div>
        <div class="h-2 bg-black/80 border border-theme-primary/40 rounded-sm overflow-hidden">
          <div
            class="h-full rounded-sm transition-[width] duration-300"
            :style="{
              width: `${relationship.affinity}%`,
              backgroundColor: 'var(--color-theme-primary)',
            }"
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
          v-if="
            relationship.relationship_type === 'romantic' ||
            relationship.relationship_type === 'partner'
          "
          @click="$emit('break-up')"
          color="error"
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
import type { Relationship } from '../../models/relationship'

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

const badgeClass = computed(() => {
  switch (props.relationship.relationship_type) {
    case 'partner':
      return 'bg-red-500/20 text-red-400 border border-red-500/30'
    case 'romantic':
      return 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
    case 'friend':
      return 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
    case 'ex':
      return 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
    default:
      return 'bg-black/40 text-theme-primary border border-theme-primary/30'
  }
})
</script>
