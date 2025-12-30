<template>
  <div class="bg-gray-800 rounded-lg p-6 border border-green-500/30">
    <h2 class="text-2xl font-bold text-green-500 mb-6">Vault Statistics</h2>

    <div v-if="statistics" class="space-y-4">
      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Dwellers Created</span>
        <span class="text-green-500 font-bold text-xl">{{ statistics.totalDwellersCreated }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Caps Earned</span>
        <span class="text-green-500 font-bold text-xl">{{ statistics.totalCapsEarned }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Explorations</span>
        <span class="text-green-500 font-bold text-xl">{{ statistics.totalExplorations }}</span>
      </div>

      <div class="flex justify-between items-center p-3 bg-gray-700/50 rounded">
        <span class="text-gray-300">Total Rooms Built</span>
        <span class="text-green-500 font-bold text-xl">{{ statistics.totalRoomsBuilt }}</span>
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
