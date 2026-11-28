<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import { formatDateTime } from '@/core/utils/format'
import type { EnvoySignal } from '../models/envoy'
import StandingMeter from './StandingMeter.vue'

const props = withDefaults(
  defineProps<{ signal: EnvoySignal; awaiting?: boolean; busy?: boolean }>(),
  { awaiting: false, busy: false }
)

const emit = defineEmits<{ hail: []; respond: [accept: boolean] }>()

type Action = 'respond' | 'awaiting' | 'transmit' | 'idle'

/** One primary action per card: answering wins over our own unanswered hail. */
const action = computed<Action>(() => {
  if (props.signal.incoming_hail) return 'respond'
  if (props.awaiting) return 'awaiting'
  if (props.signal.can_hail) return 'transmit'
  return 'idle'
})

const distance = computed(() =>
  props.signal.distance === null || props.signal.distance === undefined
    ? 'UNPLOTTED'
    : `${props.signal.distance.toFixed(1)} U`
)

// The server keeps returning a lapsed timestamp while it reopens can_hail; only a future one locks.
const lockedUntil = computed(() => {
  const locked = props.signal.locked_until ?? null
  return locked && new Date(locked) > new Date() ? locked : null
})

const idleLabel = computed(() => {
  if (lockedUntil.value) return 'LINE LOCKED'
  return props.signal.status === 'UNMET' ? 'NO LINE' : 'LINE OPEN'
})
</script>

<template>
  <Card class="gap-0 border-theme-primary/20 bg-surface-sunken py-0">
    <CardHeader class="flex flex-row items-start justify-between gap-3 px-4 pt-4 pb-2">
      <div class="min-w-0">
        <CardTitle class="text-lg font-bold tabular-nums text-theme-primary">
          VAULT {{ signal.number }}
        </CardTitle>
        <CardDescription class="mt-1 text-xs text-theme-primary/60">
          OVERSEER
          <span class="font-bold text-theme-primary/80">{{ signal.owner_username }}</span>
        </CardDescription>
      </div>
      <Badge variant="outline" class="border-theme-primary/40 tracking-[0.12em] text-theme-primary">
        {{ signal.status }}
      </Badge>
    </CardHeader>

    <CardContent class="flex flex-col gap-3 px-4 pb-4">
      <div class="grid grid-cols-2 gap-2">
        <TerminalMetric icon="mdi:map-marker-distance" label="DISTANCE" :value="distance" compact />
        <TerminalMetric
          icon="mdi:account-voice"
          label="STANDING"
          :value="signal.standing"
          compact
        />
      </div>

      <StandingMeter :standing="signal.standing" compact />

      <Alert v-if="lockedUntil" variant="destructive">
        <Icon icon="mdi:lock-outline" />
        <AlertTitle>LINE LOCKED</AlertTitle>
        <AlertDescription>
          That vault refused the last filing. The band reopens
          {{ formatDateTime(lockedUntil) }}.
        </AlertDescription>
      </Alert>

      <div class="flex items-center justify-end gap-2">
        <Button v-if="action === 'transmit'" size="sm" :disabled="busy" @click="emit('hail')">
          <Icon icon="mdi:radio-tower" :ariaHidden="true" />
          TRANSMIT
        </Button>

        <Button v-else-if="action === 'awaiting'" size="sm" variant="secondary" disabled>
          <Icon icon="mdi:timer-sand" :ariaHidden="true" />
          AWAITING REPLY
        </Button>

        <template v-else-if="action === 'respond'">
          <Button size="sm" variant="secondary" :disabled="busy" @click="emit('respond', false)">
            REFUSE
          </Button>
          <Button size="sm" :disabled="busy" @click="emit('respond', true)">
            <Icon icon="mdi:check" :ariaHidden="true" />
            ACCEPT
          </Button>
        </template>

        <span v-else class="text-xs font-bold tracking-[0.12em] text-theme-primary/50">
          {{ idleLabel }}
        </span>
      </div>
    </CardContent>
  </Card>
</template>
