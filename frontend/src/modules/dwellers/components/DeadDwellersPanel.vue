<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import type { DwellerDead } from '@/modules/dwellers/models/dweller'
import { DeadDwellerCard } from './death'

defineProps<{
  dwellers: DwellerDead[]
  isLoading: boolean
  revivingDwellers: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'revive', dwellerId: string): void
  (e: 'view-details', dwellerId: string): void
  (e: 'view-graveyard'): void
}>()
</script>

<template>
  <section>
    <div class="mb-6 flex w-full justify-end">
      <UButton variant="secondary" size="sm" @click="emit('view-graveyard')">
        <Icon icon="mdi:grave-stone" class="mr-2 h-4 w-4" />
        View Graveyard
      </UButton>
    </div>

    <div v-if="isLoading" class="w-full py-12 text-center">
      <Icon icon="mdi:loading" class="mx-auto h-12 w-12 animate-spin text-theme-primary" />
      <p class="mt-4 text-theme-primary/60">Loading deceased dwellers...</p>
    </div>

    <div
      v-else-if="dwellers.length === 0"
      class="w-full rounded-lg border border-gray-700 bg-gray-800/30 py-12 text-center"
    >
      <Icon icon="mdi:emoticon-happy" class="mx-auto mb-4 h-16 w-16 text-theme-primary/40" />
      <h3 class="mb-2 text-xl font-bold text-theme-primary">No Dead Dwellers</h3>
      <p class="text-sm text-theme-primary/60">
        All dwellers are alive and well. Check the graveyard for permanently deceased.
      </p>
      <UButton variant="secondary" size="sm" class="mt-4" @click="emit('view-graveyard')">
        <Icon icon="mdi:grave-stone" class="mr-2 h-4 w-4" />
        View Graveyard
      </UButton>
    </div>

    <div v-else class="w-full dead-dweller-grid">
      <DeadDwellerCard
        v-for="dweller in dwellers"
        :key="dweller.id"
        :dweller="dweller"
        :loading="revivingDwellers[dweller.id]"
        @revive="emit('revive', $event)"
        @view-details="emit('view-details', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.dead-dweller-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; width: 100%; }
@media (max-width: 640px) { .dead-dweller-grid { grid-template-columns: 1fr; gap: 1rem; } }
</style>
