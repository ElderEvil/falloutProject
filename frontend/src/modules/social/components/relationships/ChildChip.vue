<script setup lang="ts">
import { computed } from 'vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

interface Props {
  dweller: DwellerShort
}

const props = defineProps<Props>()

const emit = defineEmits<{ (e: 'select', dwellerId: string): void }>()

/** Full display name of the child dweller. */
const fullName = computed(() =>
  `${props.dweller.first_name} ${props.dweller.last_name ?? ''}`.trim()
)
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1.5 rounded-full border border-theme-primary/20 bg-surface-sunken px-2 py-1 text-xs text-theme-primary transition-colors hover:border-theme-primary/50 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
    @click="emit('select', dweller.id)"
  >
    <DwellerPortrait
      :thumbnail-url="dweller.thumbnail_url"
      :alt="fullName"
      prefer-thumbnail
      image-class="h-6 w-6 shrink-0 rounded-full object-cover"
      fallback-class="h-6 w-6 shrink-0 text-theme-primary/60"
    />
    <span>{{ dweller.first_name }}</span>
  </button>
</template>
