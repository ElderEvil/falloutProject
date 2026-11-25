<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { useWorldEventStore } from '../stores/worldEvent'

const props = defineProps<{ vaultId: string }>()
const store = useWorldEventStore()
const flags = useFeatureFlagsStore()

const to = computed(() => `/vault/${props.vaultId}/world-event`)

onMounted(async () => {
  // The API 404s while the event ships dark, so asking anyway costs a failed request on every
  // vault load and a console error the banner never shows. Read the flag before asking.
  if (!flags.loaded) await flags.fetchFlags()
  if (!flags.worldEvents) return
  await store.load(props.vaultId, { silent: true })
})
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
      {{ store.event?.progress_amount }} / {{ store.event?.target_amount }} ({{
        store.progressPercent
      }}%)
    </span>
    <Icon icon="mdi:chevron-right" class="h-4 w-4 shrink-0" />
  </router-link>
</template>
