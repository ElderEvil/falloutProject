<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { UCard, UAlert, UProgressBar } from '@/core/components/ui'
import USkeleton from '@/core/components/ui/USkeleton.vue'
import type { AIOperationStats, AIUsageStats } from '../models/aiUsage'

interface Props {
  stats: AIUsageStats | null
  loading?: boolean
}

const { stats, loading = false } = defineProps<Props>()

const formatNumber = (num: number): string => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

const allTimeTotal = computed(() => stats?.all_time?.total_tokens ?? 0)
const monthlyTotal = computed(() => stats?.current_month?.total_tokens ?? 0)
const monthLabel = computed(() => stats?.month ?? '')

const quotaPercentage = computed(() => stats?.quota_percentage ?? 0)
const quotaColor = computed(() => {
  const pct = quotaPercentage.value
  if (pct >= 100) return 'text-red-500'
  if (pct >= 80) return 'text-amber-500'
  return 'text-theme-primary'
})

const promptBarColor = 'rgb(74 222 128)'
const completionBarColor = 'rgb(96 165 250)'
const quotaFillColor = computed(() => {
  const pct = quotaPercentage.value
  if (pct >= 100) return 'rgb(239 68 68)'
  if (pct >= 80) return 'rgb(245 158 11)'
  return 'var(--color-theme-primary)'
})

const resetDateFormatted = computed(() => {
  if (!stats?.reset_date) return ''
  const date = new Date(stats.reset_date)
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
})

const isEmpty = computed(() => {
  if (!stats) return false
  return allTimeTotal.value === 0 && monthlyTotal.value === 0 && (stats.quota_used ?? 0) === 0
})

const operationLabels: Record<string, string> = {
  chat_with_dweller: 'Dweller chat',
  audio_chat: 'Voice chat',
  generate_backstory: 'Biography generation',
  extend_bio: 'Biography extension',
  generate_visual_attributes: 'Appearance generation',
  generate_photo: 'Portrait generation',
  generate_audio: 'Voice line generation',
}

const operationBreakdown = computed(() => {
  const monthTotal = monthlyTotal.value
  return (stats?.by_operation ?? [])
    .filter((operation) => !operation.is_operational)
    .map((operation: AIOperationStats) => ({
      ...operation,
      label: operationLabels[operation.operation] ?? 'Other AI activity',
      percentage: monthTotal > 0 ? (operation.total_tokens / monthTotal) * 100 : 0,
    }))
})

const requestLabel = (count: number): string => `${count} request${count === 1 ? '' : 's'}`

const storageKey = computed(() => {
  const month = stats?.month ?? new Date().toISOString().slice(0, 7)
  return `quota_warning_dismissed_${month}`
})

const isBannerDismissed = ref(true)

onMounted(() => {
  const dismissed = localStorage.getItem(storageKey.value)
  isBannerDismissed.value = dismissed === 'true'
})

const dismissBanner = () => {
  isBannerDismissed.value = true
  localStorage.setItem(storageKey.value, 'true')
}

const showWarningBanner = computed(() => {
  return stats?.quota_warning && !isBannerDismissed.value
})
</script>

<template>
  <UCard
    title="AI USAGE STATISTICS"
    glow
    crt
    class="!border-theme-primary/40"
  >
    <div v-if="loading" class="space-y-4">
      <USkeleton class="h-8 w-full" />
      <USkeleton class="h-16 w-full" />
      <USkeleton class="h-16 w-full" />
    </div>

    <div v-else-if="stats" class="space-y-6">
      <UAlert v-if="showWarningBanner" variant="warning" dismissible @close="dismissBanner">
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <span>
            You've used <strong>{{ Math.round(quotaPercentage) }}%</strong> of your monthly token
            quota
          </span>
          <RouterLink
            to="/profile"
            class="inline-flex items-center gap-1 text-[color:var(--color-warning)] hover:underline font-medium"
          >
            View Details
            <Icon icon="mdi:arrow-right" class="h-4 w-4" />
          </RouterLink>
        </div>
      </UAlert>

      <div
        v-if="isEmpty"
        class="text-center py-8 text-theme-primary/70 font-mono text-sm"
      >
        <Icon icon="mdi:robot-outline" class="h-10 w-10 mx-auto mb-3 opacity-50" />
        <p>No AI activity recorded yet.</p>
      </div>

      <template v-else>
        <div class="grid grid-cols-2 gap-4">
          <div class="text-center p-4 bg-surface-sunken rounded border border-theme-primary/20">
            <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-2">
              All-Time Tokens
            </div>
            <div class="text-2xl font-bold text-theme-primary terminal-glow-subtle">
              {{ formatNumber(allTimeTotal) }}
            </div>
          </div>
          <div class="text-center p-4 bg-surface-sunken rounded border border-theme-primary/20">
            <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-2">
              {{ monthLabel }} Tokens
            </div>
            <div class="text-2xl font-bold text-theme-primary terminal-glow-subtle">
              {{ formatNumber(monthlyTotal) }}
            </div>
          </div>
        </div>

        <div class="border-t border-theme-primary/20 pt-4 space-y-3">
          <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-3">
            Token Breakdown
          </div>

          <div class="flex items-center gap-3">
            <Icon icon="mdi:arrow-up-bold" class="h-5 w-5 text-green-400" />
            <div class="flex-1">
              <div class="flex justify-between text-sm">
                <span class="text-theme-primary/70">Prompt Tokens</span>
                <span class="text-theme-primary">{{
                  formatNumber(stats.all_time.prompt_tokens)
                }}</span>
              </div>
              <UProgressBar
                class="mt-1"
                :height="4"
                :glow="false"
                :color="promptBarColor"
                :model-value="
                  stats.all_time.total_tokens > 0
                    ? (stats.all_time.prompt_tokens / stats.all_time.total_tokens) * 100
                    : 0
                "
              />
            </div>
          </div>

          <div class="flex items-center gap-3">
            <Icon icon="mdi:arrow-down-bold" class="h-5 w-5 text-blue-400" />
            <div class="flex-1">
              <div class="flex justify-between text-sm">
                <span class="text-theme-primary/70">Completion Tokens</span>
                <span class="text-theme-primary">{{
                  formatNumber(stats.all_time.completion_tokens)
                }}</span>
              </div>
              <UProgressBar
                class="mt-1"
                :height="4"
                :glow="false"
                :color="completionBarColor"
                :model-value="
                  stats.all_time.total_tokens > 0
                    ? (stats.all_time.completion_tokens / stats.all_time.total_tokens) * 100
                    : 0
                "
              />
            </div>
          </div>
        </div>

        <section v-if="operationBreakdown.length" class="border-t border-theme-primary/20 pt-4 space-y-3" aria-labelledby="operation-usage-heading">
          <div>
            <h3 id="operation-usage-heading" class="text-xs text-theme-primary/70 uppercase tracking-wider">
              This Month by Operation
            </h3>
            <p class="mt-1 text-xs leading-5 text-theme-primary/55">
              Chats and optional generation count toward your monthly AI quota.
            </p>
          </div>

          <div v-for="operation in operationBreakdown" :key="operation.operation" class="space-y-1.5">
            <div class="flex items-baseline justify-between gap-3 text-sm">
              <span class="font-medium text-theme-primary">{{ operation.label }}</span>
              <span class="shrink-0 text-theme-primary/70">
                {{ formatNumber(operation.total_tokens) }} · {{ requestLabel(operation.count) }} · {{ Math.round(operation.percentage) }}%
              </span>
            </div>
            <UProgressBar
              :model-value="operation.percentage"
              :ariaLabel="`${operation.label}: ${operation.total_tokens} tokens across ${requestLabel(operation.count)}, ${Math.round(operation.percentage)}% of this month`"
              :height="5"
              :glow="false"
            />
          </div>

          <div v-if="stats.chat_heavy" class="flex items-start gap-2 rounded border border-warning/30 bg-warning/10 p-2.5 text-xs leading-5 text-warning" role="status">
            <Icon icon="mdi:message-alert-outline" class="mt-0.5 h-4 w-4 shrink-0" />
            <span v-if="stats.quota_exceeded">Most AI use this month is dwelling chat. Your quota is currently exhausted.</span>
            <span v-else>Most AI use this month is dwelling chat. Your quota is still available for any AI feature.</span>
          </div>
        </section>

        <div v-if="stats.quota_limit > 0" class="border-t border-theme-primary/20 pt-4 space-y-3">
          <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-3">
            Monthly Quota
          </div>

          <div
            class="relative h-6 bg-surface-sunken rounded border border-theme-primary/20 overflow-hidden"
          >
            <UProgressBar
              class="!rounded-none !border-0"
              :height="24"
              :glow="false"
              :color="quotaFillColor"
              :model-value="Math.min(quotaPercentage, 100)"
            />
            <div class="absolute inset-0 flex items-center justify-center text-sm font-bold">
              <span :class="quotaColor">
                {{ formatNumber(stats.quota_used) }} / {{ formatNumber(stats.quota_limit) }} ({{
                  Math.round(quotaPercentage)
                }}%)
              </span>
            </div>
          </div>

          <div class="flex justify-between items-center text-sm">
            <div class="flex items-center gap-2">
              <Icon icon="mdi:clock-outline" class="h-4 w-4 text-theme-primary/70" />
              <span class="text-theme-primary/70">
                {{ formatNumber(stats.quota_remaining) }} remaining
              </span>
            </div>
            <div v-if="resetDateFormatted" class="flex items-center gap-2">
              <Icon icon="mdi:calendar-refresh" class="h-4 w-4 text-theme-primary/70" />
              <span class="text-theme-primary/70"> Resets on {{ resetDateFormatted }} </span>
            </div>
          </div>

          <div
            v-if="stats.quota_exceeded"
            class="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm"
          >
            <Icon icon="mdi:alert-circle" class="h-4 w-4" />
            <span>Quota exceeded. Some AI features may be limited.</span>
          </div>
          <div
            v-else-if="stats.quota_warning"
            class="flex items-center gap-2 p-2 bg-amber-500/10 border border-amber-500/30 rounded text-amber-400 text-sm"
          >
            <Icon icon="mdi:alert" class="h-4 w-4" />
            <span>Approaching quota limit.</span>
          </div>
        </div>
      </template>
    </div>

    <div v-else class="text-center py-8 text-theme-primary/60">
      <Icon icon="mdi:robot-outline" class="h-12 w-12 mx-auto mb-2 opacity-50" />
      <p>No AI usage data available</p>
    </div>
  </UCard>
</template>

<style scoped>
:deep(.ai-usage-card button[aria-label='Dismiss alert']:focus-visible),
:deep([role='alert'] button[aria-label='Dismiss alert']:focus-visible) {
  outline: 2px dashed var(--color-theme-primary);
  outline-offset: 2px;
  box-shadow: 0 0 8px var(--color-theme-glow);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0s !important;
    animation-duration: 0s !important;
  }
}
</style>
