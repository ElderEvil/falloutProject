<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import type { EnvoySignal } from '../models/envoy'

const props = withDefaults(
  defineProps<{
    open: boolean
    signal: EnvoySignal | null
    ttlHours: number
    busy?: boolean
    error?: string | null
  }>(),
  { busy: false, error: null }
)

const emit = defineEmits<{ 'update:open': [open: boolean]; confirm: [] }>()

/** The band carries no free text: one canned dispatch, no message field anywhere. */
const DISPATCH =
  'UNMET VAULT, THIS IS A CALLSIGN ON EMERGENCY BAND 47.2. WE HAVE YOU ON THE ATLAS AND ARE IN RADIO RANGE. ACKNOWLEDGE THIS HAIL AND WE OPEN A LINE.'

const target = computed(() =>
  props.signal ? `VAULT ${props.signal.number} · OVERSEER ${props.signal.owner_username}` : ''
)

function close(): void {
  emit('update:open', false)
}
</script>

<template>
  <TerminalModal
    :open="open"
    title="TRANSMIT HAIL"
    icon="mdi:radio-tower"
    size="md"
    :show-close="!busy"
    @update:open="emit('update:open', $event)"
    @close="close"
  >
    <div class="flex flex-col gap-4 px-6 py-5">
      <div class="flex flex-col gap-1">
        <span class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">TO</span>
        <span class="text-sm font-bold text-theme-primary">{{ target }}</span>
      </div>

      <div class="rounded border border-theme-primary/20 bg-surface-sunken p-4">
        <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">CANNED DISPATCH</p>
        <p class="mt-2 text-sm leading-6 text-theme-primary/80">{{ DISPATCH }}</p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <TerminalMetric icon="mdi:coins" label="COST" value="0 CAPS" tone="caps" compact />
        <TerminalMetric icon="mdi:timer-sand" label="EXPIRES IN" :value="`${ttlHours} H`" compact />
      </div>

      <p class="text-xs leading-5 text-theme-primary/60">
        A hail is one canned dispatch — the band carries no free text. The answer opens the line or
        locks it; the log keeps the receipt either way.
      </p>

      <Alert v-if="error" variant="destructive">
        <Icon icon="mdi:alert-circle-outline" />
        <AlertTitle>TRANSMISSION REFUSED</AlertTitle>
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>
    </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="CANCEL"
        confirm-label="TRANSMIT"
        confirm-icon="mdi:access-point"
        :confirm-disabled="busy"
        @cancel="close"
        @confirm="emit('confirm')"
      />
    </template>
  </TerminalModal>
</template>
