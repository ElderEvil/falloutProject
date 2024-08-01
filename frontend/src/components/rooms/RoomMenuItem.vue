<script setup lang="ts">
import LockIcon from '@/components/icons/LockIcon.vue'

const props = defineProps<{
  room: Room
}>()

const emit = defineEmits<{
  (e: 'select', room: Room): void
}>()
</script>

<template>
  <li
    @click="emit('select', room)"
    class="cursor-pointer rounded bg-gray-700 p-2 text-white transition-colors duration-200 hover:bg-gray-600"
  >
    <div class="flex flex-col items-center">
      <div class="flex items-center space-x-2">
        <div>{{ room.name }}</div>
        <div v-if="room.population_required > 0">
          <LockIcon />
        </div>
      </div>
      <div class="my-2">
        <img
          :src="room.thumbnail_url"
          :alt="`${room.name} Thumbnail`"
          class="h-12 w-12 rounded-full object-cover"
        />
      </div>
      <div class="text-sm">Population required: {{ room.population_required }}</div>
    </div>
  </li>
</template>
