<script setup lang="ts">
import { computed } from 'vue'
import { Heart, Zap } from '@lucide/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'

interface CombatantAction {
  name: string
  charge: number
  queued: boolean
  pending: boolean
  enabled: boolean
}

interface Props {
  name: string
  health: number
  maxHealth: number
  tone?: 'success' | 'danger'
  action?: CombatantAction | null
}

const props = withDefaults(defineProps<Props>(), {
  tone: 'success',
  action: null,
})

const emit = defineEmits<{ skill: [] }>()

const healthPercent = computed(() =>
  props.maxHealth > 0 ? Math.min(100, Math.max(0, (props.health / props.maxHealth) * 100)) : 0
)

const actionDisabled = computed(
  () =>
    !props.action ||
    !props.action.enabled ||
    props.action.queued ||
    props.action.pending ||
    props.action.charge < 100 ||
    props.health <= 0
)

const actionPulsing = computed(
  () =>
    !!props.action &&
    props.action.enabled &&
    !props.action.queued &&
    !props.action.pending &&
    props.action.charge >= 100
)
</script>

<template>
  <div
    class="combatant-meters w-full rounded border border-theme-primary/30 bg-black/80 p-1 backdrop-blur-sm"
  >
    <span
      class="block w-full truncate text-center text-xs font-semibold text-theme-primary [text-shadow:0_1px_3px_black]"
      :title="name"
      >{{ name }}</span
    >
    <div class="flex min-h-4 items-center gap-1">
      <Heart class="size-3 shrink-0 fill-danger text-danger" aria-hidden="true" />
      <Progress
        size="xs"
        :tone="tone"
        :model-value="healthPercent"
        :label="`${name} HP`"
        :value-text="`${health}/${maxHealth}`"
      />
    </div>
    <Button
      v-if="action"
      type="button"
      variant="ghost"
      size="xs"
      class="min-h-4 h-auto w-full justify-start gap-1 p-0 text-left hover:bg-transparent disabled:cursor-default"
      :class="{ 'animate-pulse motion-reduce:animate-none': actionPulsing }"
      :disabled="actionDisabled"
      :aria-label="`Use ${action.name} for ${name}, ${action.charge}% charged${action.queued ? ', queued' : ''}`"
      @click="emit('skill')"
    >
      <Zap
        class="size-3 shrink-0 text-theme-primary"
        :class="{ 'fill-theme-primary': action.charge >= 100 }"
        aria-hidden="true"
      />
      <Progress
        size="xs"
        tone="warning"
        :model-value="action.charge"
        :label="`${name} skill charge`"
      />
    </Button>
  </div>
</template>
