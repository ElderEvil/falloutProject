<script setup lang="ts">
/**
 * DeadDwellerCard - Display component for deceased dwellers
 * @component
 */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UCard, UButton, UBadge } from '@/core/components/ui'
import type { DwellerDead } from '@/modules/dwellers/models/dweller'

interface Props {
  dweller: DwellerDead
  loading?: boolean
}

interface Emits {
  (e: 'revive', id: string): void
  (e: 'view-details', id: string): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

// Icon mapping for death causes
const deathCauseIcon = computed(() => {
  if (!props.dweller.death_cause) return 'mdi:skull'

  switch (props.dweller.death_cause) {
    case 'health': return 'mdi:heart-broken'
    case 'radiation': return 'mdi:radioactive'
    case 'incident': return 'mdi:fire'
    case 'exploration': return 'mdi:compass'
    case 'combat': return 'mdi:sword'
    default: return 'mdi:skull'
  }
})

// Formatting for death cause text
const deathCauseText = computed(() => {
  if (!props.dweller.death_cause) return 'Unknown'
  return props.dweller.death_cause.charAt(0).toUpperCase() + props.dweller.death_cause.slice(1)
})

// Warning state for imminent permanent death (less than 3 days)
const isUrgent = computed(() => {
  return (props.dweller.days_until_permanent ?? 0) < 3 && !props.dweller.is_permanently_dead
})

const daysLeftText = computed(() => {
  if (props.dweller.is_permanently_dead) return 'PERMANENTLY DEAD'
  const days = props.dweller.days_until_permanent ?? 0
  return `${days} day${days !== 1 ? 's' : ''} remaining`
})

const handleRevive = () => {
  emit('revive', props.dweller.id)
}

const handleViewDetails = () => {
  emit('view-details', props.dweller.id)
}
</script>

<template>
  <UCard
    class="dead-dweller-card h-full flex flex-col"
    :class="{ 'border-red-500/50': isUrgent && !dweller.is_permanently_dead }"
    glow
    crt
    padding="sm"
  >
    <div class="flex gap-4">
      <!-- Thumbnail Section -->
      <div class="relative w-24 h-24 shrink-0 bg-black border border-theme-primary/30 rounded overflow-hidden group cursor-pointer" @click="handleViewDetails">
        <div v-if="dweller.thumbnail_url" class="absolute inset-0 grayscale contrast-125 sepia-0">
          <img :src="dweller.thumbnail_url" :alt="dweller.first_name" class="w-full h-full object-cover opacity-70" />
        </div>
        <div v-else class="absolute inset-0 flex items-center justify-center bg-gray-900">
          <Icon icon="mdi:account" class="w-12 h-12 text-gray-600" />
        </div>

        <!-- Red tint overlay -->
        <div class="absolute inset-0 bg-red-900/30 mix-blend-overlay"></div>

        <!-- Level Badge -->
        <div class="absolute bottom-0 right-0 bg-black/80 text-theme-primary text-xs px-1.5 py-0.5 border-t border-l border-theme-primary/30 rounded-tl">
          LVL {{ dweller.level }}
        </div>
      </div>

      <!-- Content Section -->
      <div class="flex-1 min-w-0 flex flex-col gap-2">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="font-bold text-lg leading-tight truncate text-theme-primary group-hover:text-theme-glow transition-colors cursor-pointer" @click="handleViewDetails">
              {{ dweller.first_name }} {{ dweller.last_name }}
            </h3>

            <div class="flex items-center gap-2 mt-1">
              <UBadge variant="danger" size="sm" class="flex items-center gap-1">
                <Icon :icon="deathCauseIcon" class="w-3.5 h-3.5" />
                <span>{{ deathCauseText }}</span>
              </UBadge>

              <span v-if="dweller.is_permanently_dead" class="text-xs text-gray-500 font-mono">[DECEASED]</span>
            </div>
          </div>
        </div>

        <!-- Epitaph / Status -->
        <div class="text-sm text-theme-primary/70 italic line-clamp-2 min-h-[2.5rem]">
          "{{ dweller.epitaph || 'Rest in peace.' }}"
        </div>
      </div>
    </div>

    <!-- Warning / Timer -->
    <div
      class="mt-3 mb-3 text-xs font-mono flex items-center justify-between px-2 py-1 rounded bg-black/40 border"
      :class="isUrgent ? 'border-red-500/50 text-red-400 animate-pulse' : 'border-theme-primary/20 text-theme-primary/60'"
    >
      <div class="flex items-center gap-1.5">
        <Icon icon="mdi:clock-outline" class="w-3.5 h-3.5" />
        <span>{{ daysLeftText }}</span>
      </div>
      <Icon v-if="isUrgent" icon="mdi:alert" class="w-3.5 h-3.5" />
    </div>

    <!-- Actions -->
    <div class="mt-auto flex gap-2">
      <UButton
        v-if="!dweller.is_permanently_dead"
        variant="primary"
        size="sm"
        class="flex-1"
        :loading="loading"
        icon="mdi:medical-bag"
        @click="handleRevive"
      >
        REVIVE
      </UButton>
      <UButton
        v-else
        variant="secondary"
        size="sm"
        class="flex-1 opacity-50 cursor-not-allowed"
        disabled
      >
        BURIED
      </UButton>
    </div>
  </UCard>
</template>

<style scoped>
/* Scoped styles if needed, but Tailwind is preferred */
</style>
