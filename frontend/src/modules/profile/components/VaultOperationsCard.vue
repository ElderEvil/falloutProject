<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UCard } from '@/core/components/ui'
import type { UserProfile } from '../models/profile'

type VaultRecord = Pick<
  UserProfile,
  'total_dwellers_created' | 'total_caps_earned' | 'total_explorations' | 'total_rooms_built'
>

const props = withDefaults(
  defineProps<{
    record: VaultRecord
    refreshing?: boolean
  }>(),
  { refreshing: false }
)

const metrics = computed(() => [
  {
    label: 'Population',
    value: props.record.total_dwellers_created,
    detail: 'Dwellers welcomed',
    icon: 'mdi:account-group',
  },
  {
    label: 'Economy',
    value: props.record.total_caps_earned,
    detail: 'Caps earned',
    icon: 'mdi:currency-usd',
  },
  {
    label: 'Exploration',
    value: props.record.total_explorations,
    detail: 'Wasteland deployments',
    icon: 'mdi:compass',
  },
  {
    label: 'Construction',
    value: props.record.total_rooms_built,
    detail: 'Rooms commissioned',
    icon: 'mdi:office-building',
  },
])

const hasActivity = computed(() => metrics.value.some((metric) => metric.value > 0))
</script>

<template>
  <section aria-label="Vault operations">
    <UCard glow crt class="overflow-hidden !border-theme-primary/40">
      <template #header>
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center border border-theme-primary/30 bg-surface-sunken shadow-glow-sm">
              <Icon icon="mdi:chart-box-outline" class="h-6 w-6 text-theme-accent" />
            </div>
            <div>
              <p class="text-xs font-bold tracking-[0.18em] text-theme-primary/60">OVERSIGHT CONSOLE</p>
              <h2 class="mt-0.5 text-xl font-bold tracking-[0.08em] text-theme-primary terminal-glow">VAULT OPERATIONS</h2>
            </div>
          </div>
          <p
            role="status"
            aria-live="polite"
            class="inline-flex items-center gap-2 border px-2.5 py-1.5 text-xs font-bold tracking-[0.12em]"
            :class="props.refreshing ? 'border-theme-accent/50 bg-theme-accent/10 text-theme-accent' : 'border-theme-primary/30 bg-theme-primary/10 text-theme-primary'"
          >
            <Icon :icon="props.refreshing ? 'mdi:sync' : 'mdi:access-point-check'" :class="{ 'animate-spin': props.refreshing }" />
            {{ props.refreshing ? 'SYNCING RECORD' : 'RECORD LINK ACTIVE' }}
          </p>
        </div>
      </template>

      <p class="max-w-2xl text-sm leading-6 text-theme-primary/70">
        All-time activity attributed to this overseer account across every active vault.
      </p>

      <div v-if="hasActivity" class="mt-5 grid gap-px overflow-hidden border border-theme-primary/25 bg-theme-primary/25 sm:grid-cols-2 xl:grid-cols-4">
        <article v-for="metric in metrics" :key="metric.label" class="bg-surface-sunken p-4 transition-colors duration-200 hover:bg-surface-hover">
          <div class="flex items-start justify-between gap-3">
            <p class="text-xs font-bold tracking-[0.14em] text-theme-primary/65">{{ metric.label }}</p>
            <Icon :icon="metric.icon" class="h-5 w-5 shrink-0 text-theme-accent" />
          </div>
          <p class="mt-5 font-mono text-4xl font-bold tracking-tight text-theme-primary">{{ metric.value.toLocaleString('en-US') }}</p>
          <p class="mt-2 text-xs leading-5 text-theme-primary/55">{{ metric.detail }}</p>
        </article>
      </div>

      <div v-else class="mt-5 border border-dashed border-theme-primary/30 bg-surface-sunken px-5 py-8 text-center">
        <Icon icon="mdi:chart-timeline-variant-shimmer" class="mx-auto h-9 w-9 text-theme-primary/45" />
        <p class="mt-3 text-sm font-bold tracking-[0.08em] text-theme-primary/80">No vault activity reported yet.</p>
        <p class="mx-auto mt-2 max-w-md text-sm leading-6 text-theme-primary/55">Records accumulate as your vault operates.</p>
      </div>
    </UCard>
  </section>
</template>
