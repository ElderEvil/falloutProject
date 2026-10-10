<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { formatDate } from '@/core/utils/format'
import { formatRemaining } from '@/core/utils/time'
import { useCountdown } from '@/core/composables/useCountdown'
import { usePartySelection } from '@/modules/progression/composables/usePartySelection'
import PartySlots from '@/modules/progression/components/party/PartySlots.vue'
import AvailableDwellers from '@/modules/progression/components/party/AvailableDwellers.vue'
import SupplySliders from '@/modules/progression/components/party/SupplySliders.vue'
import type {
  ExpeditionSiteMarkerRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '../models/map'
import { useMapStore } from '../stores/map'
import { isHintLocation, isKnownLocation } from '../utils/visibility'

interface Props {
  modelValue: boolean
  location: WastelandLocationWithDwellers | null
  vaultMarker: VaultMarkerRead | null
  site?: ExpeditionSiteMarkerRead | null
  /** Already-filtered candidates for the in-modal Send-team section. */
  dwellers?: DwellerShort[]
  maxPartySize?: number
  /** Vault medical stock; the slider ceiling is min(stock, 15). */
  maxStimpaks?: number
  maxRadaways?: number
  /** True while the vault/dweller data feeding the Send-team section loads. */
  suppliesLoading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  site: null,
  dwellers: () => [],
  maxPartySize: 3,
  maxStimpaks: 0,
  maxRadaways: 0,
  suppliesLoading: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  /**
   * Confirmed team and supplies from the in-modal Send-team section. The map
   * routes this to the dispatch service; the detail modal itself never calls it.
   */
  (
    e: 'dispatch',
    payload: { dwellerIds: string[]; supplies: { stimpaks: number; radaways: number } }
  ): void
}>()

const router = useRouter()
const route = useRoute()
const mapStore = useMapStore()

const vaultId = computed(() => route.params.id as string)

// The marker's site-type archetype, when the place maps to a catalog group.
const placeGroup = computed(() => {
  const key = props.location?.group_key
  return key ? (mapStore.placeGroupByKey.get(key) ?? null) : null
})

const isOpen = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const isVaultMarker = computed(() => props.vaultMarker !== null && props.location === null)

const isSite = computed(
  () => props.site != null && props.location === null && props.vaultMarker === null
)

const placeName = computed(() => {
  if (props.location) return props.location.name
  if (props.vaultMarker) return props.vaultMarker.name
  if (props.site) return props.site.name
  return ''
})

const placeType = computed(() => {
  if (props.location) return props.location.type
  if (props.vaultMarker) return 'vault'
  if (props.site) return 'expedition_site'
  return ''
})

const description = computed(() => {
  if (props.location) return props.location.description ?? 'No description available.'
  if (props.vaultMarker) return props.vaultMarker.description
  if (props.site) return props.site.flavor
  return ''
})

const coordinates = computed(() => {
  const marker = props.location ?? props.vaultMarker ?? props.site
  return marker ? `${marker.coord_x}, ${marker.coord_y}` : 'Unavailable'
})

const recordStatus = computed(() => {
  if (isVaultMarker.value) return 'SIGNAL DETECTED'
  return props.location && isKnownLocation(props.location) ? 'SURVEYED' : 'UNVERIFIED'
})

const recordedAt = computed(() => {
  if (!props.location?.created_at) return 'NO DATE LOGGED'
  return formatDate(props.location.created_at)
})

const linkedDwellers = computed(() => {
  if (props.location && props.location.dwellers.length > 0) {
    return props.location.dwellers
  }
  return null
})

const badgeVariant = computed(() => {
  const map: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    home_vault: 'default',
    origin: 'outline',
    visited: 'secondary',
    discovery: 'outline',
    vault: 'destructive',
    expedition_site: 'outline',
  }
  return map[placeType.value] ?? 'secondary'
})

// `discovery` has no shadcn amber equivalent; preserve its warning colour explicitly.
const badgeClass = computed(() =>
  placeType.value === 'discovery' ? 'bg-warning text-black border-warning' : ''
)

const isLocked = computed(() => props.location !== null && isHintLocation(props.location))

// Clear-state projection for clearable map points (issue 772).
const clearState = computed(() => props.location?.clear_state ?? null)
const isClearable = computed(() => clearState.value?.clearable ?? false)
const isCleared = computed(() => clearState.value?.cleared ?? false)
// Local countdown seeded from the backend snapshot: the polled locations array
// is replaced, but the modal keeps its own selected object, so without this the
// displayed countdown (and the Dispatch button) would go stale while open.
const reclearSecondsSource = computed(() => clearState.value?.time_remaining_seconds ?? 0)
const { secondsLeft: reclearSeconds, isFinished: reclearFinished } =
  useCountdown(reclearSecondsSource)

const reclearReady = computed(() => isCleared.value && reclearFinished.value)
const reclearCountdown = computed(() =>
  reclearSeconds.value > 0 ? formatRemaining(reclearSeconds.value) : ''
)
const lootTableLabel = computed(() => clearState.value?.loot_table ?? '')

// Send-team state for the in-modal dispatch section. Dispatch mode passes the
// already-filtered candidates straight in (no eligibility fetch) and opens from
// an empty party each time the modal lands on a location.
// Suggested loadout: pre-fill 5/5 (clamped to vault stock) so sending a team is
// one click, not a slider chore.
const DISPATCH_SUPPLY_SUGGESTION = { stimpaks: 5, radaways: 5 }
const {
  selectedDwellerIds,
  selectedStimpaks,
  selectedRadaways,
  stimpakMax,
  radawayMax,
  selectedDwellers,
  canSubmit,
  toggleDweller,
  setStimpaks,
  setRadaways,
  resetOnOpen,
  suppliesPayload,
} = usePartySelection({
  dwellers: () => props.dwellers,
  maxPartySize: () => props.maxPartySize,
  maxStimpaks: () => props.maxStimpaks,
  maxRadaways: () => props.maxRadaways,
  supplySuggestion: () => DISPATCH_SUPPLY_SUGGESTION,
})

// The section and its footer confirm appear exactly where the old Dispatch
// button did: a clearable point that is uncleared or re-clearable.
const actionable = computed(() => isClearable.value && (!isCleared.value || reclearReady.value))

watch(
  () => props.modelValue,
  (open) => {
    // Reset only on open: the polled locations array replaces the selected
    // object every tick (same id, new reference), so watching the location
    // itself would wipe an in-progress party mid-selection.
    if (open && props.location) resetOnOpen([])
  },
  { immediate: true }
)

function closeModal() {
  isOpen.value = false
}

function confirmDispatch() {
  if (!canSubmit.value) return
  emit('dispatch', { dwellerIds: [...selectedDwellerIds.value], supplies: suppliesPayload() })
}

// Expedition-site status projection (mirrors the marker's block_reason).
const siteStatus = computed(() => {
  const site = props.site
  if (!site) return ''
  if (site.block_reason === 'open') return 'IN PROGRESS'
  if (site.cleared) return 'CLEARED'
  return 'READY'
})
const siteCleared = computed(() => siteStatus.value === 'CLEARED')
// Local countdown seeded from the backend snapshot (same staleness rationale
// as the location reclear timer above).
const siteCooldownSource = computed(() => props.site?.cooldown_remaining_seconds ?? 0)
const { secondsLeft: siteCooldownSeconds } = useCountdown(siteCooldownSource)

const siteCooldownCountdown = computed(() =>
  siteCooldownSeconds.value > 0 ? formatRemaining(siteCooldownSeconds.value) : ''
)

const modalTitle = computed(() => {
  if (isLocked.value) return 'Unknown Location'
  return placeName.value
})

async function goToDweller(dwellerId: string) {
  // Close, then let MapView's `?place=` cleanup (a router.replace triggered by the
  // close) run before navigating: issuing the push in the same tick lets that
  // replace cancel it, stranding the user on the map.
  isOpen.value = false
  await nextTick()
  await router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}

async function goToDwellerChat(dwellerId: string) {
  // Chat opens as a global modal on the map route via `?chat=<id>`. The marker
  // modal closes first so the two dialogs do not stack and fight for focus; the
  // map view itself stays mounted underneath, so no marker state is lost.
  // Wait out the close-triggered `?place=` cleanup, then drop `place` explicitly:
  // a stale query would reopen the marker modal behind the chat dialog.
  isOpen.value = false
  await nextTick()
  const query = { ...route.query }
  delete query.place
  query.chat = dwellerId
  await router.push({ query })
}

function dwellerDisplayName(first: string, last: string | null) {
  return last ? `${first} ${last}` : first
}
</script>

<template>
  <TerminalModal
    :open="isOpen"
    :title="modalTitle"
    :size="actionable ? '3xl' : 'xl'"
    max-height="75"
    :show-footer="actionable"
    footer-class="flex flex-row flex-shrink-0 justify-end gap-3 border-t border-theme-primary/25 bg-surface-sunken/40 px-5 pt-3 pb-5"
    @update:open="isOpen = $event"
  >
      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <div v-if="isLocked" class="flex flex-col items-center py-6 text-center">
          <Icon icon="mdi:lock-question" class="h-16 w-16 text-theme-primary/40" />
          <h3 class="mt-4 text-lg font-bold text-theme-primary">Unknown Location</h3>
          <p class="mt-2 max-w-sm text-sm leading-6 text-theme-primary/60">
            Chat with a dweller who has been here to uncover this place.
          </p>
          <div v-if="linkedDwellers" class="mt-4 w-full max-w-sm space-y-1.5 text-left">
            <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">KNOWN CONTACTS</p>
            <button
              v-for="d in linkedDwellers"
              :key="d.dweller_id"
              type="button"
              class="dweller-contact flex w-full items-center justify-between gap-3 rounded border border-theme-primary/20 bg-surface px-3 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
              @click="goToDwellerChat(d.dweller_id)"
            >
              <span class="text-sm text-theme-primary underline underline-offset-2">{{
                dwellerDisplayName(d.first_name, d.last_name)
              }}</span>
              <Icon icon="mdi:message-text-outline" class="h-4 w-4 text-theme-primary/60" />
            </button>
          </div>
        </div>
        <div v-else-if="isSite" class="space-y-5">
          <section class="rounded border border-theme-primary/20 bg-surface-sunken p-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-xs font-bold tracking-[0.14em] text-theme-primary/60">
                  EXPEDITION SITE
                </p>
                <p class="mt-1 text-sm font-bold text-theme-primary">{{ siteStatus }}</p>
              </div>
              <Badge variant="outline">expedition_site</Badge>
            </div>
            <div class="mt-4 grid grid-cols-2 gap-3">
              <TerminalMetric
                icon="mdi:map-marker"
                label="MAP COORDINATES"
                :value="coordinates"
                compact
              />
              <TerminalMetric
                icon="mdi:shield-star"
                label="MIN DWELLER LEVEL"
                :value="props.site?.min_dweller_level ?? 0"
                compact
              />
              <TerminalMetric
                icon="mdi:door"
                label="ROOMS"
                :value="props.site?.room_total ?? 0"
                compact
              />
              <TerminalMetric icon="mdi:radar" label="STATUS" :value="siteStatus" compact />
            </div>
          </section>

          <section class="border-l-2 border-theme-primary/50 bg-surface p-4">
            <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">SITE NOTES</p>
            <p class="mt-2 text-sm leading-6 text-theme-primary/85">{{ description }}</p>
          </section>

          <section v-if="siteCleared" class="border-t border-theme-primary/20 pt-4">
            <div class="flex flex-col gap-2">
              <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">CLEAR STATUS</p>
              <Badge
                variant="default"
                class="w-fit border-theme-primary bg-theme-primary/10 text-theme-primary terminal-glow"
              >
                CLEARED
              </Badge>
              <p
                v-if="siteCooldownCountdown"
                class="flex items-center gap-1.5 text-xs text-theme-primary/70"
              >
                <Icon icon="mdi:clock-outline" class="h-3.5 w-3.5" />
                Cooldown: {{ siteCooldownCountdown }}
              </p>
            </div>
          </section>
        </div>
        <div v-else class="space-y-5">
          <section class="rounded border border-theme-primary/20 bg-surface-sunken p-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="text-xs font-bold tracking-[0.14em] text-theme-primary/60">
                  WASTELAND FIELD REPORT
                </p>
                <p class="mt-1 text-sm font-bold text-theme-primary">{{ recordStatus }}</p>
              </div>
              <div class="flex flex-col items-end gap-1.5">
                <Badge :variant="badgeVariant" :class="badgeClass">{{ placeType }}</Badge>
                <span
                  v-if="placeGroup"
                  class="flex items-center gap-1 text-xs text-theme-primary/70"
                  :title="placeGroup.description"
                >
                  <Icon :icon="placeGroup.icon" class="h-3.5 w-3.5" />
                  {{ placeGroup.label }}
                </span>
              </div>
            </div>
            <div class="mt-4 grid grid-cols-2 gap-3">
              <TerminalMetric
                icon="mdi:map-marker"
                label="MAP COORDINATES"
                :value="coordinates"
                compact
              />
              <TerminalMetric icon="mdi:radar" label="STATUS" :value="recordStatus" compact />
              <TerminalMetric
                icon="mdi:calendar-outline"
                label="RECORDED"
                :value="recordedAt"
                compact
              />
              <TerminalMetric
                :icon="isVaultMarker ? 'mdi:radio-tower' : 'mdi:account-group'"
                :label="isVaultMarker ? 'MARKER TYPE' : 'KNOWN DWELLERS'"
                :value="isVaultMarker ? 'VAULT SIGNAL' : (linkedDwellers?.length ?? 0)"
                compact
              />
            </div>
          </section>

          <section class="border-l-2 border-theme-primary/50 bg-surface p-4">
            <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">SITE NOTES</p>
            <p class="mt-2 text-sm leading-6 text-theme-primary/85">{{ description }}</p>
          </section>

          <section v-if="isClearable" class="border-t border-theme-primary/20 pt-4">
            <div class="flex items-center justify-between gap-3">
              <div class="flex flex-col gap-2">
                <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">
                  CLEAR STATUS
                </p>
                <div class="flex flex-wrap items-center gap-2">
                  <Badge
                    v-if="isCleared"
                    variant="default"
                    class="border-theme-primary bg-theme-primary/10 text-theme-primary terminal-glow"
                  >
                    CLEARED ×{{ clearState?.clear_count }}
                  </Badge>
                  <Badge v-else variant="outline" class="border-warning/60 text-warning">
                    UNCLAIMED
                  </Badge>
                  <span
                    class="flex items-center gap-1 text-xs text-theme-primary/70"
                    :title="lootTableLabel || undefined"
                  >
                    <Icon icon="mdi:shield-alert" class="h-3.5 w-3.5" />
                    Tier {{ clearState?.tier }}
                  </span>
                </div>
              </div>
            </div>
            <p
              v-if="isCleared && reclearCountdown"
              class="mt-2 flex items-center gap-1.5 text-xs text-theme-primary/70"
            >
              <Icon icon="mdi:clock-outline" class="h-3.5 w-3.5" />
              Re-clear available: {{ reclearCountdown }}
            </p>
          </section>

          <section v-if="actionable" class="space-y-4 border-t border-theme-primary/20 pt-4">
            <p class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">SEND TEAM</p>
            <PartySlots
              :selected-dwellers="selectedDwellers"
              :selected-count="selectedDwellerIds.length"
              :max-party-size="maxPartySize"
              @remove="toggleDweller"
            />
            <AvailableDwellers
              :dwellers="dwellers"
              :selected-ids="selectedDwellerIds"
              :is-loading="suppliesLoading"
              :show-eligible-badge="false"
              :error="null"
              @toggle="toggleDweller"
            />
            <SupplySliders
              :selected-stimpaks="selectedStimpaks"
              :selected-radaways="selectedRadaways"
              :max-stimpaks="maxStimpaks"
              :max-radaways="maxRadaways"
              :stimpak-max="stimpakMax"
              :radaway-max="radawayMax"
              @update:stimpaks="setStimpaks"
              @update:radaways="setRadaways"
            />
          </section>

          <section v-if="linkedDwellers" class="border-t border-theme-primary/20 pt-4">
            <h4 class="mb-2 text-sm font-bold uppercase text-theme-primary">Linked Dwellers</h4>
            <ul class="space-y-1.5">
              <li v-for="d in linkedDwellers" :key="d.dweller_id">
                <button
                  type="button"
                  class="dweller-entry flex w-full items-center justify-between gap-3 rounded border border-theme-primary/20 bg-surface px-3 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
                  @click="goToDweller(d.dweller_id)"
                >
                  <span class="text-sm text-theme-primary underline underline-offset-2">{{
                    dwellerDisplayName(d.first_name, d.last_name)
                  }}</span>
                  <span class="text-xs text-theme-primary/60">{{ d.relation }}</span>
                </button>
              </li>
            </ul>
          </section>
        </div>
      </div>

    <template #footer>
        <Button variant="secondary" size="sm" @click="closeModal">Cancel</Button>
        <Button
          size="sm"
          class="border-theme-primary/40 bg-theme-primary/10 text-theme-primary hover:bg-theme-primary/20"
          :disabled="!canSubmit || suppliesLoading"
          @click="confirmDispatch"
        >
          <Icon icon="mdi:send" class="h-4 w-4" />
          Dispatch
        </Button>
    </template>
  </TerminalModal>
</template>
