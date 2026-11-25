<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { usePvpStore } from '../stores/pvp'

const props = defineProps<{ vaultId: string }>()
const store = usePvpStore()

const to = computed(() => `/vault/${props.vaultId}/pvp`)

// One line, most actionable first: a challenge waiting for a defender beats the
// vault's own outstanding challenge.
const message = computed(() => {
  const waiting = store.board.length
  if (waiting === 1) return '1 CHALLENGE AWAITS A DEFENDER'
  if (waiting > 1) return `${waiting} CHALLENGES AWAIT A DEFENDER`
  if (store.hasOpenChallenge) return 'YOUR CHALLENGE AWAITS A DEFENDER'
  return null
})

onMounted(() => store.load(props.vaultId))
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
