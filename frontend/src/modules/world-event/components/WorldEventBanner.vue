<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useWorldEventStore } from '../stores/worldEvent'

const props = defineProps<{ vaultId: string }>()
const store = useWorldEventStore()

const percent = computed(() => {
  const target = store.event?.target_amount ?? 0
  if (target <= 0) return 0
  return Math.min(100, Math.round(((store.event?.progress_amount ?? 0) / target) * 100))
})

const to = computed(() => `/vault/${props.vaultId}/world-event`)

onMounted(() => store.load(props.vaultId, { silent: true }))
</script>

<template>
  <router-link
    v-if="store.hasEvent"
    :to="to"
    class="flex items-center gap-3 rounded border border-terminal-green/40 bg-surface-raised px-4 py-2 text-sm hover:border-terminal-green"
  >
    <Icon icon="mdi:radio-tower" class="h-5 w-5 shrink-0" />
    <span class="truncate font-bold">{{ store.event?.title }}</span>
    <span class="ml-auto whitespace-nowrap text-terminal-green/70">
      {{ store.event?.progress_amount }} / {{ store.event?.target_amount }} ({{ percent }}%)
    </span>
    <Icon icon="mdi:chevron-right" class="h-4 w-4 shrink-0" />
  </router-link>
</template>
