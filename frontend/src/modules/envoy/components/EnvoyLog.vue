<script setup lang="ts">
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { Badge } from '@/core/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Skeleton } from '@/core/components/ui/skeleton'
import { formatDateTime } from '@/core/utils/format'
import type { DiplomaticFilingStatus, EnvoyFiling } from '../models/envoy'

withDefaults(
  defineProps<{
    filings: EnvoyFiling[]
    vaultLabel: (vaultId: string) => string
    counterpartyOf: (filing: EnvoyFiling) => string
    loading?: boolean
    refreshing?: boolean
  }>(),
  { loading: false, refreshing: false }
)

const STAMP: Record<DiplomaticFilingStatus, string> = {
  PENDING: 'FILED',
  ACCEPTED: 'ACCEPTED',
  REFUSED: 'REFUSED',
  EXPIRED: 'EXPIRED',
  VOID: 'EXPIRED',
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <TerminalLoadingState v-if="loading" message="Reading the filing log..." />

    <template v-else>
      <Skeleton v-if="refreshing" class="h-20 w-full" />

      <TerminalEmptyState
        v-if="!filings.length"
        icon="mdi:file-document-outline"
        title="LOG EMPTY"
        description="No filing has crossed this band. Transmit a hail and the log keeps every answer, refusal and lapse."
      />

      <Card v-else class="gap-0 border-theme-primary/20 bg-surface-sunken py-0">
        <CardHeader class="border-b border-theme-primary/20 px-4 py-3">
          <CardTitle class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">
            FILING LOG · {{ filings.length }} ENTRIES
          </CardTitle>
        </CardHeader>
        <CardContent class="px-0 py-0">
          <ol>
            <li
              v-for="filing in filings"
              :key="filing.filing_id"
              class="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-theme-primary/10 px-4 py-2.5 last:border-b-0"
            >
              <Badge
                variant="outline"
                class="w-20 justify-center border-theme-primary/40 tracking-[0.12em] text-theme-primary"
              >
                {{ STAMP[filing.status] }}
              </Badge>
              <span class="text-xs font-bold tracking-[0.12em] text-theme-primary">
                {{ filing.kind }}
              </span>
              <span class="text-xs tracking-[0.08em] text-theme-primary/60">
                {{ filing.incoming ? 'INBOUND' : 'OUTBOUND' }} ·
                {{ vaultLabel(counterpartyOf(filing)) }}
              </span>
              <span class="ml-auto text-xs tabular-nums text-theme-primary/50">
                {{ filing.created_at ? formatDateTime(filing.created_at) : 'UNSTAMPED' }}
              </span>
            </li>
          </ol>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
