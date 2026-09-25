<script setup lang="ts">
import { Icon } from '@iconify/vue'

defineProps<{ lines: string[]; subdued?: boolean }>()
</script>

<template>
  <ul v-if="lines.length > 0" class="mt-2 flex flex-col gap-1">
    <li
      v-for="(line, index) in lines"
      :key="index"
      class="flex items-center gap-1.5 text-[0.8125rem] font-semibold"
      :class="subdued ? '' : 'text-theme-primary'"
    >
      <Icon icon="mdi:chevron-right" class="h-4 w-4" />
      {{ line }}
    </li>
  </ul>
</template>
