<template>
  <div class="bg-gray-800 rounded-lg p-6 border" :style="{ borderColor: 'rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3)' }">
    <h2 class="text-2xl font-bold mb-6" :style="{ color: 'var(--color-theme-primary)' }">Vault Statistics</h2>

    <div v-if="statistics" class="space-y-4">
      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Dwellers Created</span>
        <span class="font-bold text-xl" :style="{ color: 'var(--color-theme-primary)' }">{{ statistics.totalDwellersCreated }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Caps Earned</span>
        <span class="font-bold text-xl" :style="{ color: 'var(--color-theme-primary)' }">{{ statistics.totalCapsEarned }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Explorations</span>
        <span class="font-bold text-xl" :style="{ color: 'var(--color-theme-primary)' }">{{ statistics.totalExplorations }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Rooms Built</span>
        <span class="font-bold text-xl" :style="{ color: 'var(--color-theme-primary)' }">{{ statistics.totalRoomsBuilt }}</span>
      </div>
    </div>

    <div v-else class="text-gray-400 text-center py-8">
      No statistics available
    </div>
  </div>
</template>

<script setup lang="ts">
interface Statistics {
  totalDwellersCreated: number
  totalCapsEarned: number
  totalExplorations: number
  totalRoomsBuilt: number
}

defineProps<{
  statistics: Statistics | null
}>()
</script>
