<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UCard } from '@/core/components/ui'
import type { AIUsageStats } from '../models/aiUsage'
import USkeleton from '@/core/components/ui/USkeleton.vue'

interface Props {
  stats: AIUsageStats | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const formatNumber = (num: number): string => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

const allTimeTotal = computed(() => props.stats?.all_time?.total_tokens ?? 0)
const monthlyTotal = computed(() => props.stats?.current_month?.total_tokens ?? 0)
const monthLabel = computed(() => props.stats?.month ?? '')
</script>

<template>
  <UCard title="AI USAGE STATISTICS" glow crt>
    <div v-if="loading" class="space-y-4">
      <USkeleton class="h-8 w-full" />
      <USkeleton class="h-16 w-full" />
      <USkeleton class="h-16 w-full" />
    </div>

    <div v-else-if="stats" class="space-y-6">
      <div class="grid grid-cols-2 gap-4">
        <div class="text-center p-4 bg-black/40 rounded border border-theme-primary/20">
          <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-2">All-Time Tokens</div>
          <div class="text-2xl font-bold text-theme-primary terminal-glow-subtle">
            {{ formatNumber(allTimeTotal) }}
          </div>
        </div>
        <div class="text-center p-4 bg-black/40 rounded border border-theme-primary/20">
          <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-2">
            {{ monthLabel }} Tokens
          </div>
          <div class="text-2xl font-bold text-theme-primary terminal-glow-subtle">
            {{ formatNumber(monthlyTotal) }}
          </div>
        </div>
      </div>

      <div class="border-t border-theme-primary/20 pt-4 space-y-3">
        <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-3">Token Breakdown</div>

        <div class="flex items-center gap-3">
          <Icon icon="mdi:arrow-up-bold" class="h-5 w-5 text-green-400" />
          <div class="flex-1">
            <div class="flex justify-between text-sm">
              <span class="text-theme-primary/70">Prompt Tokens</span>
              <span class="text-theme-primary">{{ formatNumber(stats.all_time.prompt_tokens) }}</span>
            </div>
            <div class="h-1 bg-theme-primary/10 rounded mt-1">
              <div
                class="h-full bg-green-400/60 rounded"
                :style="{ width: stats.all_time.total_tokens > 0 ? (stats.all_time.prompt_tokens / stats.all_time.total_tokens * 100) + '%' : '0%' }"
              />
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <Icon icon="mdi:arrow-down-bold" class="h-5 w-5 text-blue-400" />
          <div class="flex-1">
            <div class="flex justify-between text-sm">
              <span class="text-theme-primary/70">Completion Tokens</span>
              <span class="text-theme-primary">{{ formatNumber(stats.all_time.completion_tokens) }}</span>
            </div>
            <div class="h-1 bg-theme-primary/10 rounded mt-1">
              <div
                class="h-full bg-blue-400/60 rounded"
                :style="{ width: stats.all_time.total_tokens > 0 ? (stats.all_time.completion_tokens / stats.all_time.total_tokens * 100) + '%' : '0%' }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8 text-theme-primary/60">
      <Icon icon="mdi:robot-outline" class="h-12 w-12 mx-auto mb-2 opacity-50" />
      <p>No AI usage data available</p>
    </div>
  </UCard>
</template>
