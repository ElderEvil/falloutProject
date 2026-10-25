<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import BattleLog from './BattleLog.vue'
import { parseUtcMs } from '@/core/utils/time'
import { battleLogKindLabel, type BattleLogEntry } from '../models/battleLog'
import type { ArenaRosterEntry } from '../api/arena'
import type { ArenaMatchDraft } from '../composables/useArenaMatchDraft'

interface Props {
  match: ArenaMatchDraft
}

const props = defineProps<Props>()

const JOURNAL_KIND_LABELS: Record<string, string> = {
  turn: 'TURN',
  skill: 'SKILL',
  hit: 'HIT',
  finish: 'FINISH',
  reward: 'REWARD',
}

// Persisted timestamps preserve chronology across worker reloads and localize in the log.
const journalEntries = computed<BattleLogEntry[]>(() =>
  [...(props.match.roomState?.events ?? [])]
    .sort((a, b) =>
      a.created_at && b.created_at
        ? parseUtcMs(a.created_at) - parseUtcMs(b.created_at)
        : a.round_seq - b.round_seq
    )
    .map((event) => ({
      id: event.id,
      kind: battleLogKindLabel(event.kind, JOURNAL_KIND_LABELS),
      message: event.message,
      timestamp: event.created_at,
    }))
)

const hpPercent = (entry: ArenaRosterEntry) =>
  entry.max_health > 0 ? Math.round((entry.health / entry.max_health) * 100) : 0

const hpTone = (entry: ArenaRosterEntry) => {
  const pct = hpPercent(entry)
  return pct < 25 ? 'danger' : pct < 50 ? 'warning' : 'success'
}
</script>

<template>
  <div class="arena-panel flex flex-col gap-3">
    <details v-if="match.bench.length" aria-label="Arena bench" class="border-t border-border pt-2">
      <summary
        class="cursor-pointer py-1 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-ring"
      >
        Bench · {{ match.bench.length }} waiting
      </summary>

      <div class="grid gap-2 pt-2 sm:grid-cols-2 lg:grid-cols-3">
        <Card v-for="entry in match.bench" :key="entry.id" size="sm" class="gap-2 py-3">
          <CardHeader>
            <div class="flex items-start gap-2">
              <DwellerPortrait
                :image-url="entry.image_url"
                :thumbnail-url="entry.thumbnail_url"
                :alt="entry.name"
                prefer-thumbnail
                image-class="size-10 shrink-0 rounded-md object-cover"
                fallback-class="size-10 shrink-0 text-theme-primary"
              />
              <div class="flex min-w-0 flex-1 flex-col gap-1">
                <CardTitle class="break-words">{{ entry.name }}</CardTitle>
                <CardDescription>Level {{ entry.level }}</CardDescription>
              </div>
              <TooltipProvider v-if="!match.isFighting" :delay-duration="200">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      :aria-label="`Remove ${entry.name} from Arena`"
                      @click="match.unassign(entry)"
                    >
                      <Icon icon="mdi:account-minus-outline" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Remove {{ entry.name }} from Arena</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </CardHeader>
          <CardContent class="flex flex-col gap-2">
            <span class="text-xs text-muted-foreground tabular-nums"
              >{{ entry.health }} / {{ entry.max_health }} HP</span
            >
            <Progress
              :model-value="hpPercent(entry)"
              :tone="hpTone(entry)"
              :label="`${entry.name} health`"
              :value-text="`${entry.health} of ${entry.max_health} HP`"
            />
          </CardContent>
        </Card>
      </div>
    </details>

    <details aria-label="Battle journal" class="border-t border-border pt-2">
      <summary
        class="cursor-pointer py-1 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-ring"
      >
        Battle journal · {{ match.roomState?.events.length ?? 0 }} entries
      </summary>
      <div class="flex flex-col gap-2 pt-2">
        <Button
          v-if="match.roomState?.events.length"
          variant="ghost"
          size="xs"
          class="self-end"
          @click="match.clearJournal()"
          >CLEAR</Button
        >
        <BattleLog :entries="journalEntries" empty-text="No attacks yet." />
      </div>
    </details>

    <details class="text-xs text-muted-foreground">
      <summary
        class="cursor-pointer rounded-sm py-1 focus-visible:outline focus-visible:outline-ring"
      >
        Match rewards &amp; recovery
      </summary>
      <p class="pt-2 leading-relaxed">
        Teams take turns attacking, starting with Team A. Queued skills fire on their owner's next
        team turn. Skills charge as combat progresses. Hover or focus a skill for its effect.
        Winners gain happiness and XP. Losing dwellers lose happiness and are left at 1 HP. Healing
        uses carried stimpaks, or vault storage when none are carried. Check their health before the
        next fight. Change the fighters to start a new match.
      </p>
    </details>

    <div v-if="match.isDone && match.injuredFighters.length" class="flex justify-center">
      <Button
        variant="secondary"
        size="sm"
        :disabled="match.isHealing"
        @click="match.healInjured()"
      >
        <Icon v-if="match.isHealing" icon="mdi:loading" class="animate-spin" />
        <Icon v-else icon="mdi:medication" />
        HEAL INJURED ({{ match.injuredFighters.length }})
      </Button>
    </div>
  </div>
</template>
