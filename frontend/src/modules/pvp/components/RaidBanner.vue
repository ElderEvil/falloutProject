<script setup lang="ts">
import { computed, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { usePvpStore } from '../stores/pvp'

const props = defineProps<{ vaultId: string }>()
const store = usePvpStore()
const flags = useFeatureFlagsStore()

const to = computed(() => `/vault/${props.vaultId}/pvp`)

// One line, most actionable first: a challenge waiting for a defender beats the
// vault's own outstanding challenge.
const message = computed(() => {
  // With duels off the endpoints 404, so the banner would advertise a dead surface.
  if (!flags.pvpDuels) return null
  // The store keeps the last loaded vault's board; never present it as this vault's.
  if (store.stateVaultId !== props.vaultId) return null
  const waiting = store.board.length
  if (waiting === 1) return '1 CHALLENGE AWAITS A DEFENDER'
  if (waiting > 1) return `${waiting} CHALLENGES AWAIT A DEFENDER`
  if (store.hasOpenChallenge) return 'YOUR CHALLENGE AWAITS A DEFENDER'
  return null
})

// Flags arrive asynchronously (the shell fetches them), so react to the flag instead of deciding
// once on mount. ``silent`` keeps a failed background load from raising a toast at a player who
// never asked for the board.
watch(
  () => [props.vaultId, flags.pvpDuels] as const,
  ([vaultId, pvpDuels]) => {
    if (!vaultId || !pvpDuels) return
    void store.load(vaultId, undefined, { silent: true })
  },
  { immediate: true }
)
</script>

<template>
  <router-link
    v-if="message"
    :to="to"
    class="flex items-center gap-3 rounded border border-terminal-green/40 bg-surface-raised px-4 py-2 text-sm hover:border-terminal-green"
  >
    <Icon icon="mdi:sword-cross" class="h-5 w-5 shrink-0" ariaHidden="true" />
    <span class="truncate font-bold">{{ message }}</span>
    <Icon icon="mdi:chevron-right" class="ml-auto h-4 w-4 shrink-0" ariaHidden="true" />
  </router-link>
</template>
