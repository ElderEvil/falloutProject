<script setup lang="ts">
import { Icon } from '@iconify/vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Skeleton } from '@/core/components/ui/skeleton'
import { formatDateTime } from '@/core/utils/format'
import type { EnvoyFiling } from '../models/envoy'

withDefaults(
  defineProps<{
    filings: EnvoyFiling[]
    vaultLabel: (vaultId: string) => string
    loading?: boolean
    refreshing?: boolean
    busy?: boolean
  }>(),
  { loading: false, refreshing: false, busy: false }
)

const emit = defineEmits<{ respond: [filing: EnvoyFiling, accept: boolean] }>()
</script>

<template>
  <div class="flex flex-col gap-3">
    <TerminalLoadingState v-if="loading" message="Opening the filing tray..." />

    <template v-else>
      <Skeleton v-if="refreshing" class="h-24 w-full" />

      <TerminalEmptyState
        v-if="!filings.length"
        icon="mdi:inbox-outline"
        title="NO FILINGS WAITING"
        description="Nothing addressed to this vault is pending an answer. A hail lands here the moment another overseer transmits."
      />

      <ul v-else class="flex flex-col gap-3">
        <li v-for="filing in filings" :key="filing.filing_id">
          <Card class="gap-0 border-theme-primary/20 bg-surface-sunken py-0">
            <CardHeader class="flex flex-row items-start justify-between gap-3 px-4 pt-4 pb-2">
              <div class="min-w-0">
                <CardTitle class="text-base font-bold text-theme-primary">
                  {{ filing.kind }} FROM {{ vaultLabel(filing.from_vault_id) }}
                </CardTitle>
                <CardDescription class="mt-1 text-xs text-theme-primary/60">
                  Filed {{ filing.created_at ? formatDateTime(filing.created_at) : 'UNSTAMPED' }} ·
                  expires
                  {{ formatDateTime(filing.expires_at) }}
                </CardDescription>
              </div>
              <Badge
                variant="outline"
                class="border-theme-primary/40 tracking-[0.12em] text-theme-primary"
              >
                PENDING
              </Badge>
            </CardHeader>
            <CardContent class="flex items-center justify-between gap-3 px-4 pb-4">
              <p class="text-xs leading-5 text-theme-primary/60">
                Accepting opens the line and pays the first contact. Refusing locks the band for
                this pair.
              </p>
              <div class="flex shrink-0 items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  :disabled="busy"
                  @click="emit('respond', filing, false)"
                >
                  <Icon icon="mdi:close" :ariaHidden="true" />
                  REFUSE
                </Button>
                <Button size="sm" :disabled="busy" @click="emit('respond', filing, true)">
                  <Icon icon="mdi:check" :ariaHidden="true" />
                  ACCEPT
                </Button>
              </div>
            </CardContent>
          </Card>
        </li>
      </ul>
    </template>
  </div>
</template>
