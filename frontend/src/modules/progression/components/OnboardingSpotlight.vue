<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useElementBounding, usePreferredReducedMotion } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Alert } from '@/core/components/ui/alert'
import { Card } from '@/core/components/ui/card'
import { usePolling } from '@/core/composables/usePolling'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useObjectiveClaim } from '../composables/useObjectiveClaim'
import { useOnboardingState } from '@/core/composables/useOnboardingState'
import { isOverlayBlocking, isOnlyBlockingOverlay } from '@/core/composables/useBlockingOverlay'
import {
  ORIENTATION_STEPS,
  type OnboardingLesson,
  type TeachingEligibility,
  type TeachingSnapshot,
} from '../models'
import { currentObjective as lowestUnfinishedStarter } from '../models/objective'
import type { Objective } from '../models/objective'
import ObjectiveCompleteModal from './ObjectiveCompleteModal.vue'
import IntroHandoffCard from './IntroHandoffCard.vue'

const store = useObjectivesStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const dwellerStore = useDwellerStore()
const auth = useAuthStore()
const reducedMotion = usePreferredReducedMotion()
const route = useRoute()
const router = useRouter()

const vaultId = computed(() =>
  route.path.startsWith('/vault/') && typeof route.params.id === 'string' ? route.params.id : null
)

const {
  vaultState: readVaultState,
  patch,
  teaching,
  acknowledgeLesson,
  skipLesson,
  skipTour,
} = useOnboardingState()

const vaultState = computed(() => readVaultState(vaultId.value))
const teachingState = computed(() => teaching(vaultId.value))
const ledger = computed(() => teachingState.value.lessons)
const replayMode = computed(() => teachingState.value.replayOrientation)

const objectiveByKey = computed(() => {
  const byKey = new Map<string, Objective>()
  for (const objective of store.objectives) {
    if (objective.template_key && objective.vault_id === vaultId.value)
      byKey.set(objective.template_key, objective)
  }
  return byKey
})

const objectiveFor = (lesson: OnboardingLesson): Objective | undefined =>
  lesson.templateKeys
    ?.map((key) => objectiveByKey.value.get(key))
    .find((objective) => objective !== undefined)

const isHandled = (lesson: OnboardingLesson): boolean => {
  if (ledger.value[lesson.id]) return true
  // Explicit replay reaches claimed steps; otherwise a claimed objective retires the lesson.
  return !replayMode.value && objectiveFor(lesson)?.is_completed === true
}

const pendingLessons = computed(() => ORIENTATION_STEPS.filter((lesson) => !isHandled(lesson)))
const currentLesson = computed(() => pendingLessons.value[0])
const lessonObjective = computed(() => {
  const lesson = currentLesson.value
  return lesson ? objectiveFor(lesson) : undefined
})

const optedIn = computed(() => !!vaultState.value.created || replayMode.value)
const welcomePending = computed(() => !!vaultState.value.created && !vaultState.value.welcomed)
const active = computed(
  () => !!vaultId.value && !vaultState.value.skipped && optedIn.value && !!currentLesson.value
)
const showHandoff = computed(
  () =>
    !!vaultId.value &&
    optedIn.value &&
    !vaultState.value.skipped &&
    !replayMode.value &&
    !vaultState.value.handoffDismissed &&
    !currentLesson.value &&
    ORIENTATION_STEPS.some(
      (lesson) => lesson.id === 'orientation.departure' && objectiveFor(lesson)?.is_completed
    )
)
const showWelcome = computed(() => active.value && welcomePending.value)
const showLesson = computed(() => active.value && !showWelcome.value && !!currentLesson.value)

const lowestStarterId = computed(() => {
  const current = lowestUnfinishedStarter(store.objectives)
  return current?.category === 'starter' ? current.id : undefined
})
const isServerCurrent = computed(
  () => !!lessonObjective.value && lessonObjective.value.id === lowestStarterId.value
)
const earned = computed(() => {
  const objective = lessonObjective.value
  return !!objective && objective.progress >= objective.total
})
const ready = computed(() => !replayMode.value && earned.value && isServerCurrent.value)
const needsEarlierClaim = computed(
  () =>
    !replayMode.value &&
    currentLesson.value?.kind === 'objective-explanation' &&
    !!lessonObjective.value &&
    !isServerCurrent.value
)

const showContinue = computed(() => {
  const lesson = currentLesson.value
  return !!lesson && (replayMode.value || lesson.kind !== 'objective-explanation')
})

const snapshot = computed<TeachingSnapshot>(() => ({
  vault: vaultId.value ? (vaultStore.loadedVaults[vaultId.value] ?? null) : null,
  buildableRooms: roomStore.availableRooms,
  builtRooms: roomStore.rooms,
  roomsLoaded: !!vaultId.value && roomStore.roomsLoadedVaultId === vaultId.value,
  dwellers: dwellerStore.filter.allDwellers,
  dwellersLoaded: !!vaultId.value && dwellerStore.filter.allDwellersLoadedVaultId === vaultId.value,
  objectives: store.objectives,
}))
const lessonEligibility = computed<TeachingEligibility>(() => {
  const lesson = currentLesson.value
  return earned.value ? 'eligible' : lesson ? lesson.eligibility(snapshot.value) : 'unknown'
})
const actionable = computed(() => lessonEligibility.value === 'eligible')
const blockedReason = computed(() => {
  if (needsEarlierClaim.value)
    return 'Claim your earlier starter reward before continuing this step.'
  const eligibility = lessonEligibility.value
  return typeof eligibility === 'object' ? eligibility.blocked : undefined
})

const {
  claiming,
  error: claimError,
  claim,
  clearError: clearClaimError,
} = useObjectiveClaim(vaultId)

watch([() => currentLesson.value?.id, vaultId], () => clearClaimError())

watch(
  [currentLesson, () => vaultId.value, () => auth.token],
  () => {
    const lesson = currentLesson.value
    const token = auth.token
    if (!lesson || !vaultId.value || !token) return
    if (lesson.id === 'orientation.housing') {
      if (roomStore.availableRooms.length === 0) {
        void roomStore.fetchBuildableRooms(token, vaultId.value)
      }
      if (roomStore.roomsLoadedVaultId !== vaultId.value) {
        void roomStore.fetchRooms(vaultId.value, token)
      }
    }
    if (
      lesson.id === 'orientation.departure' &&
      dwellerStore.filter.allDwellersLoadedVaultId !== vaultId.value
    ) {
      void dwellerStore.filter.fetchAllDwellers(vaultId.value, token)
    }
  },
  { immediate: true }
)

const loadFailed = ref(false)
const claimedObjective = ref<Objective | null>(null)
const handoffCard = ref<InstanceType<typeof IntroHandoffCard> | null>(null)
watch(vaultId, () => {
  claimedObjective.value = null
})
const refresh = () => {
  if (!vaultId.value || vaultState.value.skipped) return
  void handoffCard.value?.refresh()
  store
    .fetchObjectives(vaultId.value)
    .then(() => {
      loadFailed.value = false
    })
    .catch(() => {
      loadFailed.value = true
    })
}
watch([vaultId, () => route.fullPath], () => refresh(), { immediate: true })
usePolling(refresh, { interval: 30_000, immediate: false })

const targetEl = ref<HTMLElement | null>(null)
// The first anchor rendered on this page regardless of viewport position, so an
// off-screen control can be scrolled to instead of "navigated" to in place.
const presentAnchorEl = ref<HTMLElement | null>(null)

/** True while a dialog or confirmation owns attention; the guide yields to it. */
const guidingRoomMenu = computed(
  () =>
    currentLesson.value?.id === 'orientation.housing' &&
    !earned.value &&
    !needsEarlierClaim.value &&
    actionable.value &&
    isOnlyBlockingOverlay('room-menu')
)
const blockedByOverlay = computed(() => isOverlayBlocking.value && !guidingRoomMenu.value)

function hasSize(element: HTMLElement): boolean {
  if (
    element.matches(':disabled, [aria-disabled="true"]') ||
    element.closest('[hidden], [inert], [aria-hidden="true"]')
  )
    return false
  if (getComputedStyle(element).visibility === 'hidden') return false
  const rect = element.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0
}

function isUsableAnchor(element: HTMLElement): boolean {
  if (!hasSize(element)) return false
  const rect = element.getBoundingClientRect()
  let left = Math.max(0, rect.left)
  let right = Math.min(window.innerWidth, rect.right)
  let top = Math.max(0, rect.top)
  let bottom = Math.min(window.innerHeight, rect.bottom)
  // A node can be inside the viewport but clipped by a scrolling panel.
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent)
    const bounds = parent.getBoundingClientRect()
    if (/(auto|scroll|hidden|clip)/.test(style.overflowX)) {
      left = Math.max(left, bounds.left)
      right = Math.min(right, bounds.right)
    }
    if (/(auto|scroll|hidden|clip)/.test(style.overflowY)) {
      top = Math.max(top, bounds.top)
      bottom = Math.min(bottom, bounds.bottom)
    }
  }
  if (right <= left || bottom <= top) return false
  const hit = document.elementFromPoint?.((left + right) / 2, (top + bottom) / 2)
  return !hit || element.contains(hit)
}

function anchorCandidates(): HTMLElement[] {
  const keys = guidingRoomMenu.value
    ? document.querySelector('[data-onboarding="build-living-room"]')
      ? ['build-living-room']
      : ['room-search']
    : (currentLesson.value?.anchors ?? [])
  return keys.flatMap((key) => [
    ...document.querySelectorAll<HTMLElement>(`[data-onboarding="${key}"]`),
  ])
}

function resolveTarget() {
  const candidates = anchorCandidates()
  presentAnchorEl.value = candidates.find(hasSize) ?? null
  targetEl.value = candidates.find(isUsableAnchor) ?? null
  // Re-measure once the ref settles so a target chosen on scroll/resize is ready
  // in the same frame as the cut-out that depends on its bounds.
  void nextTick(() => updateBounds())
}
watch([() => currentLesson.value?.id, showWelcome, guidingRoomMenu], () => resolveTarget(), {
  flush: 'post',
})

let observer: MutationObserver | null = null
onMounted(() => {
  resolveTarget()
  observer = new MutationObserver((records) => {
    if (
      records.some(
        ({ target }) =>
          !(target instanceof Element) || !target.closest('.onboarding-card, .onboarding-cutout')
      )
    )
      resolveTarget()
  })
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: [
      'data-onboarding',
      'class',
      'style',
      'hidden',
      'aria-hidden',
      'disabled',
      'aria-disabled',
      'inert',
    ],
  })
})
onBeforeUnmount(() => observer?.disconnect())

const { top, left, width, height, update: updateBounds } = useElementBounding(targetEl)
const rectReady = computed(() => width.value > 0 && height.value > 0)
const showCutout = computed(
  () =>
    showLesson.value &&
    !earned.value &&
    !needsEarlierClaim.value &&
    actionable.value &&
    targetEl.value !== null &&
    rectReady.value
)
const cutoutStyle = computed(() => ({
  top: `${top.value - 4}px`,
  left: `${left.value - 4}px`,
  width: `${width.value + 8}px`,
  height: `${height.value + 8}px`,
}))

const viewportHeight = ref(typeof window === 'undefined' ? 0 : window.innerHeight || 0)

// Scroll and resize change which anchor is on screen (an off-screen control
// scrolled into view, or a control hidden by a narrower layout), so re-resolve
// then instead of only on mutations and lesson changes.
let anchorFrame = 0
const refreshViewport = () => {
  if (anchorFrame) return
  anchorFrame = requestAnimationFrame(() => {
    anchorFrame = 0
    viewportHeight.value = window.innerHeight || 0
    resolveTarget()
  })
}
onMounted(() => {
  window.addEventListener('resize', refreshViewport)
  // Capture catches scrolling inside panels (the side panel has its own scroller).
  window.addEventListener('scroll', refreshViewport, { capture: true, passive: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', refreshViewport)
  window.removeEventListener('scroll', refreshViewport, { capture: true })
  if (anchorFrame) cancelAnimationFrame(anchorFrame)
})

// The card sits opposite the control being explained, so it never covers it on
// small screens; when the control is below the fold the card reduces itself so
// the lesson stays visible without pushing the control off-screen. Placement
// reads the reactive element bounds, so scroll and resize update it too.
const anchorBelowFold = computed(() => {
  if (!viewportHeight.value || height.value <= 0) return false
  return top.value + height.value / 2 > viewportHeight.value / 2
})
const cardPlacement = computed(() => (anchorBelowFold.value ? 'top' : 'bottom'))

// A manual toggle wins until the lesson changes; data refreshes never reopen or
// re-collapse the card or move focus.
const userCollapsed = ref<boolean | null>(null)
const collapsed = computed(() => userCollapsed.value ?? (!earned.value && anchorBelowFold.value))
const cardClass = computed(() => [
  'onboarding-card',
  `onboarding-card--${cardPlacement.value}`,
  {
    'onboarding-card--collapsed': collapsed.value,
    'onboarding-card--modal': guidingRoomMenu.value,
  },
])
const toggleCollapsed = () => {
  userCollapsed.value = !collapsed.value
}
watch(
  () => currentLesson.value?.id,
  () => {
    userCollapsed.value = null
  }
)

const navPath = computed(() => {
  const lesson = currentLesson.value
  if (!lesson || !vaultId.value) return undefined
  if (needsEarlierClaim.value) return `/vault/${vaultId.value}/objectives`
  if (lesson.route === undefined) return undefined
  return lesson.route ? `/vault/${vaultId.value}/${lesson.route}` : `/vault/${vaultId.value}`
})
const navLabel = computed(() =>
  needsEarlierClaim.value ? 'Open Starter' : (currentLesson.value?.routeLabel ?? 'Open')
)
// The control is on this page but out of view: scroll to it rather than pushing
// the same route, which would navigate nowhere. Position for the anchor is
// re-resolved after the scroll by the existing MutationObserver + layout watch.
const showScrollToControl = computed(
  () =>
    !earned.value && !needsEarlierClaim.value && !!presentAnchorEl.value && targetEl.value === null
)
const scrollToControl = () => {
  presentAnchorEl.value?.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'center',
  })
  // Re-resolve now so the spotlight is restored even if the programmatic scroll
  // raises no scroll event (or the element was already inside the viewport).
  refreshViewport()
}
const showNavigate = computed(
  () =>
    !ready.value &&
    !guidingRoomMenu.value &&
    !!navPath.value &&
    (needsEarlierClaim.value || (targetEl.value === null && presentAnchorEl.value === null))
)
const navigateToLesson = () => {
  if (navPath.value) void router.push(navPath.value)
}

const start = () => patch(vaultId.value, { welcomed: true })
const skipTourAction = () => skipTour(vaultId.value)
const skipStepAction = () => {
  const lesson = currentLesson.value
  if (lesson) skipLesson(vaultId.value, lesson.id)
}
const continueLesson = () => {
  const lesson = currentLesson.value
  if (lesson) acknowledgeLesson(vaultId.value, lesson.id)
}

function onClaim() {
  const objective = lessonObjective.value
  const lesson = currentLesson.value
  if (!objective || !lesson) return
  void claim(objective.id, (claimed) => {
    acknowledgeLesson(vaultId.value, lesson.id)
    claimedObjective.value = claimed
  })
}
</script>

<template>
  <Teleport to="body">
    <template v-if="active">
      <div
        v-if="showCutout"
        class="onboarding-cutout"
        :class="{
          'onboarding-cutout--static': reducedMotion === 'reduce',
          'onboarding-cutout--off': blockedByOverlay,
          'onboarding-cutout--modal': guidingRoomMenu,
        }"
        :style="cutoutStyle"
        aria-hidden="true"
      />
      <Card
        v-if="!blockedByOverlay"
        :class="cardClass"
        v-bind="{ role: 'region', 'aria-live': 'polite', 'aria-label': 'Vault onboarding' }"
      >
        <template v-if="showWelcome">
          <p class="onboarding-eyebrow">VAULT-TEC // ORIENTATION</p>
          <h2 class="onboarding-title">Welcome, Overseer</h2>
          <p class="onboarding-body">
            You run this vault. Keep power, food and water flowing, put dwellers where their SPECIAL
            fits, and grow. This guide shows you one thing to do at a time.
          </p>
          <div class="onboarding-actions">
            <Button size="sm" @click="start">Start</Button>
            <Button size="sm" variant="ghost" @click="skipTourAction">Skip tour</Button>
          </div>
        </template>
        <template v-else-if="currentLesson">
          <div class="onboarding-heading">
            <p class="onboarding-eyebrow">NEXT STEP</p>
            <Button
              variant="ghost"
              size="sm"
              class="onboarding-collapse"
              v-bind="{
                type: 'button',
                'aria-expanded': !collapsed,
                'aria-controls': 'onboarding-guide-body',
                'aria-label': collapsed ? 'Expand guide' : 'Collapse guide',
              }"
              @click="toggleCollapsed"
            >
              {{ collapsed ? 'Expand' : 'Collapse' }}
            </Button>
          </div>
          <h2 class="onboarding-title">{{ currentLesson.title }}</h2>
          <div v-show="!collapsed" id="onboarding-guide-body" class="onboarding-details">
            <p class="onboarding-body">
              {{
                ready
                  ? 'This step is complete. Claim your reward to continue.'
                  : needsEarlierClaim
                    ? 'Finish and claim the earlier starter objective first. Your progress here is saved.'
                    : guidingRoomMenu
                      ? 'Choose Living room from this menu. Use search if needed, then select an adjacent empty slot in your vault.'
                      : currentLesson.body
              }}
            </p>
            <p v-if="replayMode" class="onboarding-note">
              Replay explains the controls; you do not need to repeat actions.
            </p>
            <p v-if="lessonObjective" class="onboarding-progress">
              {{ lessonObjective.progress }} / {{ lessonObjective.total }}
            </p>
            <div class="onboarding-actions">
              <Button v-if="ready" size="sm" :disabled="claiming" @click="onClaim">
                {{ claiming ? 'Claiming…' : `Claim ${lessonObjective?.reward}` }}
              </Button>
              <Button
                v-else-if="showContinue"
                size="sm"
                :disabled="claiming"
                @click="continueLesson"
              >
                Continue
              </Button>
              <Button
                v-if="showScrollToControl"
                size="sm"
                variant="outline"
                :disabled="claiming"
                @click="scrollToControl"
              >
                Show control
              </Button>
              <Button
                v-if="showNavigate"
                size="sm"
                variant="outline"
                :disabled="claiming"
                @click="navigateToLesson"
              >
                {{ navLabel }}
              </Button>
              <Button size="sm" variant="ghost" :disabled="claiming" @click="skipStepAction">
                Skip step
              </Button>
              <Button size="sm" variant="ghost" :disabled="claiming" @click="skipTourAction">
                Skip tour
              </Button>
              <Button
                v-if="loadFailed"
                size="sm"
                variant="outline"
                :disabled="claiming"
                @click="refresh"
              >
                Retry
              </Button>
            </div>
            <Alert v-if="loadFailed" class="onboarding-note">
              Could not refresh the guide. Retry.
            </Alert>
            <Alert v-if="blockedReason" class="onboarding-note">{{ blockedReason }}</Alert>
            <Alert v-if="claimError" variant="destructive" class="onboarding-error">
              {{ claimError }}
            </Alert>
          </div>
        </template>
      </Card>
    </template>
    <IntroHandoffCard
      v-if="showHandoff && vaultId"
      v-show="!blockedByOverlay"
      :key="vaultId"
      ref="handoffCard"
      :vault-id="vaultId"
      class="onboarding-card"
      @dismiss="patch(vaultId, { handoffDismissed: true })"
    />
  </Teleport>
  <ObjectiveCompleteModal
    :objective="claimedObjective"
    :show="!!claimedObjective"
    @close="claimedObjective = null"
    @confirm="claimedObjective = null"
  />
</template>

<style scoped>
/* The dimming is one box with a huge spread shadow; interaction is never blocked.
   It fades out while a modal is open so the next click is not dulled. */
.onboarding-cutout {
  position: fixed;
  z-index: 60;
  pointer-events: none;
  border-radius: 6px;
  box-shadow: 0 0 0 100vmax rgb(0 0 0 / 0.7);
  transition: opacity 0.2s ease-out;
  animation: onboarding-pulse 1.6s ease-in-out infinite;
}

.onboarding-cutout--modal {
  z-index: 1001;
}

.onboarding-card.onboarding-card--modal {
  z-index: 1002;
}

.onboarding-cutout--off {
  opacity: 0;
}

.onboarding-cutout--static {
  animation: none;
}

@keyframes onboarding-pulse {
  0%,
  100% {
    outline: 2px solid var(--color-theme-primary);
    outline-offset: 2px;
  }
  50% {
    outline: 4px solid var(--color-theme-primary);
    outline-offset: 6px;
  }
}

.onboarding-card {
  position: fixed;
  z-index: 61;
  right: 1rem;
  bottom: 1rem;
  left: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: 26rem;
  margin: 0 auto;
  padding: 1rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 8px;
  background: var(--color-surface-raised);
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  box-shadow: 0 0 18px color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
}

@media (min-width: 640px) {
  .onboarding-card {
    right: 1.5rem;
    bottom: 1.5rem;
    left: auto;
    margin: 0;
  }
}

/* Placed opposite the highlighted control so the card never covers it. */
.onboarding-card--top {
  top: 1rem;
  bottom: auto;
}

@media (min-width: 640px) {
  .onboarding-card--top {
    top: 1.5rem;
    bottom: auto;
  }
}

.onboarding-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.onboarding-collapse {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-theme-accent);
  font-family: inherit;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
}

.onboarding-collapse:hover {
  color: var(--color-theme-primary);
}

.onboarding-eyebrow {
  margin: 0;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--color-theme-accent);
}

.onboarding-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.onboarding-body {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.4;
  color: color-mix(in srgb, var(--color-theme-primary) 75%, transparent);
}

.onboarding-progress {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
}

.onboarding-note {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 0.7rem;
  color: var(--color-theme-accent);
}

.onboarding-error {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: 0.7rem;
  color: var(--color-danger);
}

.onboarding-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

@media (prefers-reduced-motion: reduce) {
  .onboarding-cutout {
    animation: none;
  }
}
</style>
