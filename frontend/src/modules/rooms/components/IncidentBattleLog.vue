<script setup lang="ts">
import { computed } from 'vue'
import type { Incident } from '@/modules/combat/models/incident'
import { battleLogKindLabel, type BattleLogEntry } from '../models/battleLog'
import BattleLog from './BattleLog.vue'

const props = defineProps<{ events: Incident['events'] }>()

const KIND_LABELS: Record<string, string> = {
  spawned: 'ALERT',
  spread: 'SPREAD',
  responders_assigned: 'RESPONDERS',
  responders_dispatched: 'DISPATCHED',
  turn: 'TURN',
  hit: 'HIT',
  round: 'ROUND',
  containment: 'CONTAINMENT',
  resolved: 'RESOLVED',
  failed: 'FAILED',
  overflow: 'LOOT',
}

const skippedNames = (data: Incident['events'][number]['data']): string[] => {
  const skipped = data?.skipped
  return Array.isArray(skipped)
    ? skipped.filter((name): name is string => typeof name === 'string')
    : []
}

const entries = computed<BattleLogEntry[]>(() =>
  props.events.map((event) => {
    // Truncated to match the round summary the backend writes, so a line never
    // reads "dealt 4 damage" next to a fractional threat delta.
    const damageToThreat = Math.trunc(Number(event.data?.damage_to_threat ?? 0))
    const damageToDwellers = Math.trunc(Number(event.data?.damage_to_dwellers ?? 0))
    const containment = Number(event.data?.amount ?? 0)
    const skipped = skippedNames(event.data)
    return {
      id: event.id,
      kind: battleLogKindLabel(event.kind, KIND_LABELS),
      message: event.message,
      meta: skipped.length ? `Unavailable: ${skipped.join(', ')}` : null,
      delta:
        damageToThreat > 0
          ? `-${damageToThreat} threat`
          : damageToDwellers > 0
            ? `-${damageToDwellers} dwellers`
            : containment > 0
              ? `+${Math.round(containment * 100)}% contained`
              : null,
    }
  })
)
</script>

<template>
  <details aria-label="Battle journal" class="border-t border-border pt-2">
    <summary
      class="cursor-pointer py-1 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-ring"
    >
      Battle log · {{ entries.length }} entries
    </summary>
    <BattleLog class="pt-2" :entries="entries" empty-text="No rounds fought yet." />
  </details>
</template>
