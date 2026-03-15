<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { UCard, UAlert } from '@/core/components/ui'
import USkeleton from '@/core/components/ui/USkeleton.vue'
import type { AIUsageStats } from '../models/aiUsage'

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

const quotaPercentage = computed(() => props.stats?.quota_percentage ?? 0)
const quotaColor = computed(() => {
  const pct = quotaPercentage.value
  if (pct >= 100) return 'text-red-500'
  if (pct >= 80) return 'text-amber-500'
  return 'text-theme-primary'
})

const quotaBarColor = computed(() => {
  const pct = quotaPercentage.value
  if (pct >= 100) return 'bg-red-500'
  if (pct >= 80) return 'bg-amber-500'
  return 'bg-theme-primary'
})

const resetDateFormatted = computed(() => {
  if (!props.stats?.reset_date) return ''
  const date = new Date(props.stats.reset_date)
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
})

// Warning banner dismissal with localStorage persistence
const storageKey = computed(() => {
  const month = props.stats?.month ?? new Date().toISOString().slice(0, 7) // YYYY-MM
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
  return props.stats?.quota_warning && !isBannerDismissed.value
})
</script>

<template>
  <UCard title="AI USAGE STATISTICS" glow crt>
    <div v-if="loading" class="space-y-4">
      <USkeleton class="h-8 w-full" />
      <USkeleton class="h-16 w-full" />
      <USkeleton class="h-16 w-full" />
    </div>

    <div v-else-if="stats" class="space-y-6">
      <!-- Warning Banner -->
      <UAlert
        v-if="showWarningBanner"
        variant="warning"
        dismissible
        @close="dismissBanner"
      >
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <span>
            You've used <strong>{{ Math.round(quotaPercentage) }}%</strong> of your monthly token quota
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

      <!-- Quota Progress Section -->
      <div v-if="stats.quota_limit > 0" class="border-t border-theme-primary/20 pt-4 space-y-3">
        <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-3">Monthly Quota</div>

        <!-- Progress Bar -->
        <div class="relative h-6 bg-black/40 rounded border border-theme-primary/20 overflow-hidden">
          <div
            class="h-full transition-all duration-300"
            :class="quotaBarColor"
            :style="{ width: Math.min(quotaPercentage, 100) + '%' }"
          />
          <div class="absolute inset-0 flex items-center justify-center text-sm font-bold">
            <span :class="quotaPercentage >= 100 ? 'text-red-500' : quotaPercentage >= 80 ? 'text-amber-500' : 'text-theme-primary'">
              {{ formatNumber(stats.quota_used) }} / {{ formatNumber(stats.quota_limit) }} ({{ Math.round(quotaPercentage) }}%)
            </span>
          </div>
        </div>

        <!-- Remaining and Reset Info -->
        <div class="flex justify-between items-center text-sm">
          <div class="flex items-center gap-2">
            <Icon icon="mdi:clock-outline" class="h-4 w-4 text-theme-primary/60" />
            <span class="text-theme-primary/70">
              {{ formatNumber(stats.quota_remaining) }} remaining
            </span>
          </div>
          <div v-if="resetDateFormatted" class="flex items-center gap-2">
            <Icon icon="mdi:calendar-refresh" class="h-4 w-4 text-theme-primary/60" />
            <span class="text-theme-primary/70">
              Resets on {{ resetDateFormatted }}
            </span>
          </div>
        </div>

        <!-- Warning/Exceeded Alert -->
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
    </div>

    <div v-else class="text-center py-8 text-theme-primary/60">
      <Icon icon="mdi:robot-outline" class="h-12 w-12 mx-auto mb-2 opacity-50" />
      <p>No AI usage data available</p>
    </div>
  </UCard>
</template>
