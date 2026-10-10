<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { ChatDebug } from '../models/chat'

interface Props {
  debug: ChatDebug | null
}

const { debug } = defineProps<Props>()

const hasGuardrail = computed(() => Boolean(debug?.guardrail?.ran))
const guardrailLabel = computed(() => {
  if (!debug?.guardrail?.ran) return 'not run'
  return debug.guardrail.blocked ? `blocked (${debug.guardrail.reason ?? 'reason n/a'})` : 'allow'
})
const tokenTotal = computed(() => debug?.total_tokens ?? 0)
</script>

<template>
  <div class="rounded-md border border-theme-primary/40 bg-terminal-background/80 p-3 font-mono text-xs">
    <div class="mb-2 flex items-center gap-1.5 text-theme-primary/70 uppercase tracking-[0.05em]">
      <Icon icon="mdi:bug-outline" class="h-3.5 w-3.5" />
      <span>Chat debug</span>
    </div>

    <div v-if="!debug" class="text-theme-primary/50">Send a message to capture a turn.</div>

    <div v-else class="flex flex-col gap-1.5">
      <div class="flex flex-wrap gap-x-4 gap-y-1">
        <span class="text-theme-primary/60"
          >model <span class="text-theme-primary">{{ debug.model ?? 'n/a' }}</span></span
        >
        <span class="text-theme-primary/60"
          >provider <span class="text-theme-primary">{{ debug.provider ?? 'n/a' }}</span></span
        >
        <span class="text-theme-primary/60"
          >tokens <span class="text-theme-primary">{{ tokenTotal }}</span>
          <span class="text-theme-primary/40"
            >({{ debug.prompt_tokens ?? 0 }} in / {{ debug.completion_tokens ?? 0 }} out)</span
          ></span
        >
      </div>

      <div class="text-theme-primary/60">
        guardrail
        <span :class="debug.guardrail?.blocked ? 'text-red-400' : 'text-emerald-400'">{{
          guardrailLabel
        }}</span>
      </div>

      <div v-if="debug.jev_decisions?.length" class="text-theme-primary/60">
        jev
        <span v-for="decision in debug.jev_decisions" :key="decision.name" class="mr-2 text-theme-primary">
          {{ decision.name }}:{{
            Object.entries(decision.fields ?? {})
              .map(([f, v]) => `${f}=${v.answer ? 'yes' : 'no'}(${v.confidence.toFixed(2)})`)
              .join(' ')
          }}
        </span>
      </div>
    </div>
  </div>
</template>
