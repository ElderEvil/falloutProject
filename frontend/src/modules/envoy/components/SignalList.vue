<script setup lang="ts">
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Skeleton } from '@/core/components/ui/skeleton'
import type { EnvoySignal } from '../models/envoy'
import SignalCard from './SignalCard.vue'

withDefaults(
  defineProps<{
    signals: EnvoySignal[]
    awaiting: Set<string>
    loading?: boolean
    refreshing?: boolean
    busy?: boolean
  }>(),
  { loading: false, refreshing: false, busy: false }
)

const emit = defineEmits<{
  hail: [signal: EnvoySignal]
  respond: [signal: EnvoySignal, accept: boolean]
}>()
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-2">
      <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">
        {{ signals.length }} SIGNALS ON THE BAND
      </p>
      <p v-if="refreshing" class="text-xs font-bold tracking-[0.12em] text-theme-primary/50">
        SWEEPING…
      </p>
    </div>

    <TerminalLoadingState v-if="loading" message="Sweeping the emergency band..." />

    <template v-else>
      <Skeleton v-if="refreshing" class="h-28 w-full" />

      <TerminalEmptyState
        v-if="!signals.length"
        icon="mdi:radio-tower"
        title="NO SIGNALS"
        description="No other vault is transmitting. The atlas lists every live vault; this band stays silent until one has a slot and a callsign."
      />

      <ul v-else class="flex flex-col gap-3">
        <li v-for="signal in signals" :key="signal.vault_id">
          <SignalCard
            :signal="signal"
            :awaiting="awaiting.has(signal.vault_id)"
            :busy="busy"
            @hail="emit('hail', signal)"
            @respond="(accept) => emit('respond', signal, accept)"
          />
        </li>
      </ul>
    </template>
  </div>
</template>
