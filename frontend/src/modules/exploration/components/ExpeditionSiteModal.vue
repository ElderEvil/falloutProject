<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/core/components/ui/dialog'
import { Progress } from '@/core/components/ui/progress'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import { isTerminal, useExpeditionSiteStore } from '../stores/expeditionSite'

interface Props {
  show: boolean
  explorationId: string
  dwellerName?: string
  timeRemainingSeconds?: number
  explorationActive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  dwellerName: '',
  timeRemainingSeconds: undefined,
  explorationActive: true,
})

const emit = defineEmits<{
  close: []
  updated: []
}>()

const store = useExpeditionSiteStore()
const confirmingRetreat = ref(false)
const closing = ref(false)

// Gap 4.3: never render a room that belongs to a different exploration.
const room = computed(() => {
  const current = store.room
  if (!current) return null
  return current.exploration_id === props.explorationId ? current : null
})
const hasOutcome = computed(() => !!room.value?.outcome)
const isTerminalRun = computed(() => (room.value ? isTerminal(room.value.status) : false))
const isDefeated = computed(() => !!room.value?.defeated && !isTerminalRun.value)
// Gap 1.6: a run left open on a non-active exploration is close-only.
const isRecovery = computed(() => !props.explorationActive && !!room.value)
const timeRemainingMinutes = computed(() => {
  if (props.timeRemainingSeconds === undefined) return null
  return Math.max(1, Math.ceil(props.timeRemainingSeconds / 60))
})
const timeExpiryWarning = computed(() => (props.timeRemainingSeconds ?? Infinity) < 300)
const isCombatRoom = computed(() => room.value?.node.kind === 'combat')
// Dedupe the room's enemy roster so duplicates read as counts, not a repeated list.
const enemySummary = computed(() => {
  const names = room.value?.node.enemy_names ?? []
  const counts = new Map<string, number>()
  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1)
  return [...counts.entries()].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(', ')
})

// Per-enemy engagement results, in fight order (present only after a resolve).
const combatOutcome = computed(() => room.value?.outcome?.combat ?? [])

// Dweller HP readout in the header. Hidden when the backend reports no max health.
const showHealthBar = computed(() => (room.value?.dweller_max_health ?? 0) > 0)
const healthRatio = computed(() => {
  const max = room.value?.dweller_max_health ?? 0
  if (max <= 0) return 0
  return Math.min(1, (room.value?.dweller_health ?? 0) / max)
})
const healthPercent = computed(() => Math.round(healthRatio.value * 100))
const healthTone = computed<'default' | 'warning' | 'danger'>(() => {
  if (healthRatio.value < 0.3) return 'danger'
  if (healthRatio.value < 0.6) return 'warning'
  return 'default'
})
const healthToneText = computed(() => {
  switch (healthTone.value) {
    case 'danger':
      return 'text-danger'
    case 'warning':
      return 'text-warning'
    default:
      return 'text-theme-primary'
  }
})
const showTimer = computed(
  () => !isTerminalRun.value && !isRecovery.value && timeRemainingMinutes.value !== null
)

// Brief "-N" flash on the HP bar whenever a resolve lands damage.
const damageFlash = ref<number | null>(null)
let damageFlashTimer: ReturnType<typeof setTimeout> | undefined

watch(
  () => room.value?.outcome,
  (outcome) => {
    if (outcome && outcome.damage_taken > 0) {
      damageFlash.value = outcome.damage_taken
      clearTimeout(damageFlashTimer)
      damageFlashTimer = setTimeout(() => {
        damageFlash.value = null
      }, 1600)
    }
  },
  { immediate: true }
)

onUnmounted(() => clearTimeout(damageFlashTimer))

watch(
  () => props.show,
  (isVisible, wasVisible) => {
    if (isVisible && !wasVisible) {
      closing.value = false
      confirmingRetreat.value = false
      // Reconnect: a room already in the store (or fetched by the view) wins
      // over the picker; otherwise load the available sites fresh.
      if (!room.value) {
        store.fetchAvailableSites(props.explorationId).catch(() => {})
      }
    }
  },
  { immediate: true }
)

const handleEnter = (siteId: string) => {
  store.enterSite(props.explorationId, siteId).catch(() => {})
}

const handleResolve = (choiceId?: string) => {
  store.resolveNode(props.explorationId, choiceId).catch(() => {})
}

const handleRetreat = () => {
  store.retreat(props.explorationId).catch(() => {})
}

const handleTerminalClose = () => {
  if (closing.value) return
  closing.value = true
  store.reset()
  emit('close')
  emit('updated')
}

const handleRecoveryClose = () => {
  if (closing.value) return
  closing.value = true
  store.reset()
  emit('close')
}

const handleDialogClose = () => {
  if (closing.value) return
  if (isRecovery.value) {
    handleRecoveryClose()
  } else if (room.value && isTerminal(room.value.status)) {
    handleTerminalClose()
  } else {
    emit('close')
  }
}

const successOdds = (odds: number): string => `${Math.round(odds * 100)}%`

const outcomeLines = computed(() => {
  const outcome = room.value?.outcome
  if (!outcome) return []
  const lines: string[] = []
  if (outcome.damage_taken > 0) lines.push(`${outcome.damage_taken} damage taken`)
  if (outcome.caps_gained > 0) lines.push(`+${outcome.caps_gained} caps`)
  if (outcome.loot_gained && outcome.loot_gained.length > 0)
    lines.push(outcome.loot_gained.join(', '))
  return lines
})

const terminalBanner = computed(() => {
  if (!room.value) return null
  switch (room.value.status) {
    case 'cleared':
      return {
        icon: 'mdi:check-decagram',
        text: 'Site cleared — rewards added to the expedition haul.',
        note: room.value.finale_paid ? 'Finale vault paid out.' : '',
        classes: 'border-theme-primary/40 bg-theme-primary/10 text-theme-primary',
      }
    case 'retreated':
      return {
        icon: 'mdi:arrow-u-left-top',
        text: 'Retreated with whatever was carried.',
        note: '',
        classes: 'border-warning/40 bg-warning/10 text-warning',
      }
    case 'died':
      return {
        icon: 'mdi:skull',
        text: 'The dweller died in the site.',
        note: '',
        classes: 'border-danger/40 bg-danger/10 text-danger',
      }
    default:
      return null
  }
})
</script>

<template>
  <Dialog
    :open="show"
    @update:open="
      (open) => {
        if (!open) handleDialogClose()
      }
    "
  >
    <DialogContent
      class="flex max-h-[75vh] w-full max-w-xl flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-xl"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-2 border-b border-theme-primary/25 bg-theme-primary/5 pt-6 pr-14 pb-4 pl-6"
      >
        <Icon icon="mdi:radio-tower" class="inline h-6 w-6 shrink-0 text-theme-primary" />
        <DialogTitle class="truncate text-2xl font-bold text-theme-primary terminal-glow">
          {{ room ? room.site_name : 'Expedition Site' }}
        </DialogTitle>
      </DialogHeader>

      <div
        v-if="room && (showHealthBar || showTimer)"
        class="flex flex-shrink-0 items-center gap-4 border-b border-theme-primary/25 bg-surface-sunken/40 px-6 py-2"
      >
        <div v-if="showHealthBar" class="flex items-center gap-2">
          <span class="text-[0.6875rem] font-semibold" :class="healthToneText">
            HP {{ room.dweller_health }}/{{ room.dweller_max_health }}
          </span>
          <Progress
            :model-value="healthPercent"
            size="xs"
            :tone="healthTone"
            class="w-28"
            :label="`Dweller health ${room.dweller_health}/${room.dweller_max_health}`"
            :value-text="`${healthPercent}%`"
          />
          <span
            v-if="damageFlash !== null"
            class="damage-flash text-[0.6875rem] font-bold text-danger"
            aria-hidden="true"
          >
            -{{ damageFlash }}
          </span>
        </div>
        <div
          v-if="showTimer"
          class="ml-auto flex items-center gap-1 rounded-[3px] border px-2 py-1 text-[0.75rem] font-semibold"
          :class="
            timeExpiryWarning
              ? 'border-warning/50 bg-warning/10 text-warning'
              : 'border-theme-primary/40 bg-theme-primary/10 text-theme-primary'
          "
          :title="
            timeExpiryWarning ? 'Clock expiry will force a retreat' : 'Exploration time remaining'
          "
        >
          <Icon
            :icon="timeExpiryWarning ? 'mdi:clock-alert-outline' : 'mdi:clock-outline'"
            class="h-3.5 w-3.5"
          />
          ≈{{ timeRemainingMinutes }}m
        </div>
      </div>

      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <!-- PICKER: no active run -->
        <template v-if="!room">
          <p v-if="dwellerName" class="mb-4 text-sm text-theme-primary/70">
            Where should {{ dwellerName }} scout?
          </p>

          <div
            v-if="store.isLoading"
            class="flex flex-col items-center gap-3 py-10 text-theme-primary/70"
          >
            <Icon icon="mdi:loading" class="h-8 w-8 animate-spin" />
            <p class="text-sm">Scanning the wasteland…</p>
          </div>

          <div
            v-else-if="store.error"
            class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
          >
            {{ store.error }}
          </div>

          <div
            v-else-if="store.availableSites.length === 0"
            class="flex flex-col items-center gap-3 py-10 text-theme-primary/60"
          >
            <Icon icon="mdi:map-marker-off" class="h-10 w-10" />
            <p class="text-center text-sm">No sites available — level up or come back later</p>
          </div>

          <div v-else class="flex flex-col gap-3">
            <div
              v-for="site in store.availableSites"
              :key="site.id"
              class="rounded-md border-2 border-theme-primary/30 bg-surface-sunken p-4 transition-colors duration-200 hover:border-theme-primary/60"
            >
              <div class="mb-2 flex items-start justify-between gap-3">
                <h4
                  class="text-base font-bold text-theme-primary [text-shadow:0_0_6px_var(--color-theme-glow)]"
                >
                  {{ site.name }}
                </h4>
                <Button size="sm" :disabled="store.isLoading" @click="handleEnter(site.id)">
                  <Icon icon="mdi:login" class="h-4 w-4" />
                  Enter
                </Button>
              </div>
              <p class="mb-3 text-sm leading-relaxed text-theme-primary/80">{{ site.flavor }}</p>
              <div class="flex flex-wrap gap-2">
                <span
                  class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
                >
                  <Icon icon="mdi:account-star" class="h-3.5 w-3.5" />
                  Lv {{ site.min_dweller_level }}
                </span>
                <span
                  class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
                >
                  <Icon icon="mdi:door" class="h-3.5 w-3.5" />
                  {{ site.room_total }} rooms
                </span>
              </div>
            </div>
          </div>
        </template>

        <!-- ACTIVE RUN -->
        <template v-else>
          <div class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span
              class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
            >
              <Icon icon="mdi:map-marker-path" class="h-3.5 w-3.5" />
              Room {{ room.room_index + 1 }} / {{ room.room_total }}
            </span>
            <span class="text-lg font-bold text-theme-primary">{{ room.room_name }}</span>
          </div>

          <p class="mb-4 text-sm leading-relaxed text-theme-primary/80">{{ room.flavor }}</p>

          <!-- RECOVERY: run open on a non-active exploration (Gap 1.6) -->
          <div
            v-if="isRecovery"
            class="mb-4 flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm font-semibold text-warning"
          >
            <Icon icon="mdi:clock-alert-outline" class="mt-0.5 h-5 w-5 shrink-0" />
            <span>This expedition has ended — the site run is closed.</span>
          </div>

          <!-- Outcome readout (the defeat banner carries its own copy) -->
          <div
            v-if="hasOutcome && !isDefeated"
            class="mb-4 rounded-md border border-theme-primary/30 bg-surface-sunken p-4 text-sm leading-relaxed text-theme-primary/90"
          >
            <p>{{ room.outcome?.text }}</p>
            <ul v-if="outcomeLines.length > 0" class="mt-2 flex flex-col gap-1">
              <li
                v-for="(line, index) in outcomeLines"
                :key="index"
                class="flex items-center gap-1.5 text-[0.8125rem] font-semibold text-theme-primary"
              >
                <Icon icon="mdi:chevron-right" class="h-4 w-4" />
                {{ line }}
              </li>
            </ul>
          </div>

          <!-- Terminal banner (terminal runs, incl. recovery) -->
          <div
            v-if="terminalBanner"
            class="mb-4 flex items-start gap-2 rounded-md border p-3 text-sm font-bold"
            :class="terminalBanner.classes"
          >
            <Icon :icon="terminalBanner.icon" class="mt-0.5 h-5 w-5 shrink-0" />
            <span>
              {{ terminalBanner.text }}
              <span v-if="terminalBanner.note" class="block text-xs font-normal opacity-80">
                {{ terminalBanner.note }}
              </span>
            </span>
          </div>

          <!-- ACTIVE ROOM: live actions only -->
          <template v-if="!isTerminalRun && !isRecovery">
            <!-- Room-pane error (Gap 4.2): visible where the failed action happened -->
            <div
              v-if="store.error"
              class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
            >
              {{ store.error }}
            </div>

            <!-- Defeat banner (Gap 3) -->
            <div
              v-if="isDefeated"
              class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-4 text-sm leading-relaxed text-danger"
            >
              <p class="mb-1 flex items-center gap-2 font-bold">
                <Icon icon="mdi:skull-crossbones" class="h-5 w-5" />
                Defeated
              </p>
              <p>{{ room.outcome?.text }}</p>
              <ul v-if="outcomeLines.length > 0" class="mt-2 flex flex-col gap-1">
                <li
                  v-for="(line, index) in outcomeLines"
                  :key="index"
                  class="flex items-center gap-1.5 text-[0.8125rem] font-semibold"
                >
                  <Icon icon="mdi:chevron-right" class="h-4 w-4" />
                  {{ line }}
                </li>
              </ul>
            </div>

            <p class="mb-4 text-base font-semibold text-theme-primary">{{ room.node.prompt }}</p>

            <div
              v-if="enemySummary || combatOutcome.length > 0"
              class="mb-4 rounded-md border px-3 py-2 text-sm font-semibold"
              :class="
                isCombatRoom
                  ? 'border-danger/40 bg-danger/10 text-danger'
                  : 'border-warning/40 bg-warning/10 text-warning'
              "
            >
              <!-- COMBAT: pre-fight deduped pack preview -->
              <div
                v-if="isCombatRoom && combatOutcome.length === 0"
                class="flex items-center gap-2"
              >
                <Icon icon="mdi:sword-cross" class="h-4 w-4" />
                <span>Enemies: {{ enemySummary }}</span>
              </div>

              <!-- COMBAT: per-enemy results after a resolve -->
              <ul v-else-if="isCombatRoom" class="flex flex-col gap-1.5">
                <li
                  v-for="entry in combatOutcome"
                  :key="entry.enemy"
                  class="flex items-center gap-2"
                >
                  <Icon
                    :icon="entry.victory ? 'mdi:skull-outline' : 'mdi:sword-cross'"
                    class="h-4 w-4 shrink-0"
                    :class="entry.victory ? 'text-theme-primary/50' : 'text-danger'"
                  />
                  <span
                    class="text-sm font-semibold"
                    :class="entry.victory ? 'text-theme-primary/50 line-through' : 'text-danger'"
                  >
                    {{ entry.enemy }}
                  </span>
                  <span
                    class="text-[0.75rem] font-semibold"
                    :class="entry.victory ? 'text-theme-primary/50' : 'text-danger'"
                  >
                    {{ entry.victory ? 'defeated' : 'overpowered' }}
                  </span>
                  <span
                    v-if="entry.damage_taken > 0"
                    class="ml-auto text-[0.75rem] font-bold text-danger"
                  >
                    -{{ entry.damage_taken }}
                  </span>
                </li>
              </ul>

              <!-- NON-COMBAT: failure-branch threat -->
              <div v-else class="flex items-center gap-2">
                <Icon icon="mdi:alert-outline" class="h-4 w-4" />
                <span>If it goes wrong: {{ enemySummary }}</span>
              </div>
            </div>

            <!-- DEFEAT: push on retries the fight -->
            <Button
              v-if="isDefeated"
              class="w-full"
              size="lg"
              :disabled="store.isLoading"
              @click="handleResolve()"
            >
              <Icon icon="mdi:sword-cross" class="h-5 w-5" />
              Push on
            </Button>

            <!-- Normal node options -->
            <template v-else>
              <div
                v-if="room.node.options && room.node.options.length > 0"
                class="flex flex-col gap-2"
              >
                <Button
                  v-for="option in room.node.options"
                  :key="option.id"
                  class="justify-between gap-2 border-theme-primary/40 bg-theme-primary/10 text-left text-theme-primary hover:bg-theme-primary/20"
                  variant="outline"
                  size="lg"
                  :disabled="store.isLoading"
                  @click="handleResolve(option.id)"
                >
                  <span class="flex-1">{{ option.label }}</span>
                  <span
                    class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-surface-sunken px-1.5 py-0.5 text-[0.75rem] font-semibold"
                  >
                    <Icon icon="mdi:brain" class="h-3.5 w-3.5" />
                    {{ option.stat }}
                  </span>
                  <span
                    class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-surface-sunken px-1.5 py-0.5 text-[0.75rem] font-semibold"
                  >
                    <Icon icon="mdi:percent" class="h-3.5 w-3.5" />
                    {{ successOdds(option.success_odds) }}
                  </span>
                </Button>
              </div>

              <Button
                v-else
                class="w-full"
                size="lg"
                :disabled="store.isLoading"
                @click="handleResolve()"
              >
                <Icon
                  :icon="room.node.kind === 'finale' ? 'mdi:lock-open-variant' : 'mdi:arrow-right'"
                  class="h-5 w-5"
                />
                {{ room.node.kind === 'finale' ? 'Open the Vault' : 'Continue' }}
              </Button>
            </template>
          </template>
        </template>
      </div>

      <DialogFooter
        class="flex flex-shrink-0 justify-end border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
      >
        <!-- PICKER footer -->
        <Button v-if="!room" variant="secondary" size="lg" @click="emit('close')">
          <Icon icon="mdi:close" class="h-5 w-5" />
          Cancel
        </Button>

        <!-- RECOVERY footer: close-only (Gap 1.6) -->
        <Button v-else-if="isRecovery" class="w-full" size="lg" @click="handleRecoveryClose">
          <Icon icon="mdi:check-bold" class="h-5 w-5" />
          Close
        </Button>

        <!-- TERMINAL footer -->
        <Button v-else-if="isTerminalRun" class="w-full" size="lg" @click="handleTerminalClose">
          <Icon icon="mdi:check-bold" class="h-5 w-5" />
          Close
        </Button>

        <!-- ROOM footer: retreat with confirm step -->
        <template v-else>
          <div v-if="confirmingRetreat" class="flex w-full flex-col items-end gap-2">
            <p class="flex items-center gap-1.5 text-xs font-semibold text-warning">
              <Icon icon="mdi:calendar-clock" class="h-3.5 w-3.5" />
              Retreating puts the site on a 7-day cooldown.
            </p>
            <TerminalModalActions
              cancel-label="Keep Exploring"
              confirm-label="Retreat"
              confirm-icon="mdi:arrow-u-left-top"
              :confirm-disabled="store.isLoading"
              @cancel="confirmingRetreat = false"
              @confirm="handleRetreat"
            />
          </div>
          <Button
            v-else-if="room.can_retreat"
            variant="secondary"
            size="lg"
            :disabled="store.isLoading"
            @click="confirmingRetreat = true"
          >
            <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5" />
            Retreat
          </Button>
        </template>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
/* Brief "-N" damage flash on the dweller HP bar: rises and fades out. */
.damage-flash {
  animation: damage-flash 1.6s ease-out forwards;
}

@keyframes damage-flash {
  0% {
    opacity: 0;
    transform: translateY(2px);
  }
  15% {
    opacity: 1;
  }
  70% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateY(-6px);
  }
}
</style>
