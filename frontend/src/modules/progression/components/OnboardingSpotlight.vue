<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useElementBounding, usePreferredReducedMotion } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useObjectiveClaim } from '../composables/useObjectiveClaim'
import { useOnboardingState } from '@/core/composables/useOnboardingState'
import { isOverlayBlocking } from '@/core/composables/useBlockingOverlay'
import {
  ORIENTATION_STEPS,
  type OnboardingLesson,
  type TeachingEligibility,
  type TeachingSnapshot,
} from '../models'
import { currentObjective as lowestUnfinishedStarter } from '../models/objective'
import type { Objective } from '../models/objective'

const store = useObjectivesStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const dwellerStore = useDwellerStore()
const auth = useAuthStore()
const toast = useToast()
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
    if (objective.template_key) byKey.set(objective.template_key, objective)
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
const blockedByEarlier = computed(() => !replayMode.value && earned.value && !isServerCurrent.value)
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
  dwellersLoaded:
    !!vaultId.value && dwellerStore.filter.allDwellersLoadedVaultId === vaultId.value,
  objectives: store.objectives,
}))
const lessonEligibility = computed<TeachingEligibility>(() => {
  const lesson = currentLesson.value
  return lesson ? lesson.eligibility(snapshot.value) : 'unknown'
})
const actionable = computed(() => lessonEligibility.value === 'eligible')
const blockedReason = computed(() => {
  const eligibility = lessonEligibility.value
  return typeof eligibility === 'object' ? eligibility.blocked : undefined
})

const { claiming, error: claimError, claim, clearError: clearClaimError } =
  useObjectiveClaim(vaultId)

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
const refresh = () => {
  if (!vaultId.value || vaultState.value.skipped) return
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
const blockedByOverlay = isOverlayBlocking

function hasSize(element: HTMLElement): boolean {
  const rect = element.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0
}

function isUsableAnchor(element: HTMLElement): boolean {
  const rect = element.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return false
  const viewportWidth = window.innerWidth || 0
  const viewportHeight = window.innerHeight || 0
  return rect.bottom > 0 && rect.top < viewportHeight && rect.right > 0 && rect.left < viewportWidth
}

function anchorCandidates(): HTMLElement[] {
  return (currentLesson.value?.anchors ?? [])
    .map((key) => document.querySelector<HTMLElement>(`[data-onboarding="${key}"]`))
    .filter((element): element is HTMLElement => element !== null)
}

function resolveTarget() {
  const candidates = anchorCandidates()
  presentAnchorEl.value = candidates.find(hasSize) ?? null
  targetEl.value = candidates.find(isUsableAnchor) ?? null
}
watch([() => currentLesson.value?.id, showWelcome], () => resolveTarget(), { flush: 'post' })

let observer: MutationObserver | null = null
onMounted(() => {
  resolveTarget()
  observer = new MutationObserver(() => resolveTarget())
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributeFilter: ['data-onboarding'],
  })
})
onBeforeUnmount(() => observer?.disconnect())

const { top, left, width, height } = useElementBounding(targetEl)
const rectReady = computed(() => width.value > 0 && height.value > 0)
const showCutout = computed(
  () => showLesson.value && actionable.value && targetEl.value !== null && rectReady.value
)
const cutoutStyle = computed(() => ({
  top: `${top.value - 4}px`,
  left: `${left.value - 4}px`,
  width: `${width.value + 8}px`,
  height: `${height.value + 8}px`,
}))

const viewportHeight = ref(typeof window === 'undefined' ? 0 : window.innerHeight || 0)
const onResize = () => {
  viewportHeight.value = window.innerHeight || 0
}
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

// The card sits opposite the control being explained, so it never covers it on
// small screens; when the control is below the fold the card reduces itself so
// the lesson stays visible without pushing the control off-screen.
const anchorBelowFold = computed(() => {
  if (!viewportHeight.value || !targetEl.value) return false
  return targetEl.value.getBoundingClientRect().top > viewportHeight.value / 2
})
const cardPlacement = computed(() => (anchorBelowFold.value ? 'top' : 'bottom'))

// A manual toggle wins until the lesson changes; data refreshes never reopen or
// re-collapse the card or move focus.
const userCollapsed = ref<boolean | null>(null)
const collapsed = computed(() => userCollapsed.value ?? anchorBelowFold.value)
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
  if (!lesson || lesson.route === undefined || !vaultId.value) return undefined
  return lesson.route ? `/vault/${vaultId.value}/${lesson.route}` : `/vault/${vaultId.value}`
})
const navLabel = computed(() => currentLesson.value?.routeLabel ?? 'Open')
// The control is on this page but out of view: scroll to it rather than pushing
// the same route, which would navigate nowhere. Position for the anchor is
// re-resolved after the scroll by the existing MutationObserver + layout watch.
const showScrollToControl = computed(
  () => !!presentAnchorEl.value && targetEl.value === null
)
const scrollToControl = () => {
  presentAnchorEl.value?.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'center',
  })
}
const showNavigate = computed(
  () => !!navPath.value && targetEl.value === null && presentAnchorEl.value === null
)
const navigateToLesson = () => {
  if (navPath.value) void router.push(navPath.value)
}
const openStarter = () => {
  if (vaultId.value) void router.push(`/vault/${vaultId.value}/objectives`)
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
    toast.success(`${claimed.reward} claimed`)
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
        }"
        :style="cutoutStyle"
        aria-hidden="true"
      />
      <section
        v-if="!blockedByOverlay"
        class="onboarding-card"
        :class="[`onboarding-card--${cardPlacement}`, { 'onboarding-card--collapsed': collapsed }]"
        role="region"
        aria-live="polite"
        aria-label="Vault onboarding"
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
            <button
              type="button"
              class="onboarding-collapse"
              :aria-expanded="!collapsed"
              aria-controls="onboarding-guide-body"
              :aria-label="collapsed ? 'Expand guide' : 'Collapse guide'"
              @click="toggleCollapsed"
            >
              {{ collapsed ? 'Expand' : 'Collapse' }}
            </button>
          </div>
          <h2 class="onboarding-title">{{ currentLesson.title }}</h2>
          <div v-show="!collapsed" id="onboarding-guide-body" class="onboarding-details">
            <p class="onboarding-body">{{ currentLesson.body }}</p>
            <p v-if="lessonObjective" class="onboarding-progress">
              {{ lessonObjective.progress }} / {{ lessonObjective.total }}
            </p>
            <div class="onboarding-actions">
            <Button v-if="ready" size="sm" :disabled="claiming" @click="onClaim">
              {{ claiming ? 'Claiming…' : `Claim ${lessonObjective?.reward}` }}
            </Button>
            <Button v-else-if="showContinue" size="sm" :disabled="claiming" @click="continueLesson">
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
            <Button
              v-if="blockedByEarlier"
              size="sm"
              variant="outline"
              :disabled="claiming"
              @click="openStarter"
            >
              Open Starter
            </Button>
            <Button size="sm" variant="ghost" :disabled="claiming" @click="skipStepAction">
              Skip step
            </Button>
            <Button size="sm" variant="ghost" :disabled="claiming" @click="skipTourAction">
              Skip tour
            </Button>
            <Button v-if="loadFailed" size="sm" variant="outline" :disabled="claiming" @click="refresh">
              Retry
            </Button>
          </div>
          <p v-if="loadFailed" class="onboarding-note">Could not refresh the guide. Retry.</p>
          <p v-if="blockedReason" class="onboarding-note">{{ blockedReason }}</p>
          <p v-if="blockedByEarlier" class="onboarding-note">
            Claim your earlier reward in Starter first.
          </p>
          <p v-if="claimError" class="onboarding-error" role="alert">{{ claimError }}</p>
          </div>
        </template>
      </section>
    </template>
  </Teleport>
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
  font-size: 0.7rem;
  color: var(--color-theme-accent);
}

.onboarding-error {
  margin: 0;
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
