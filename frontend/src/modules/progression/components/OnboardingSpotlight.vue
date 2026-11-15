<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useElementBounding, usePreferredReducedMotion } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Alert } from '@/core/components/ui/alert'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
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
  ORIENTATION_CHAPTERS,
  type OnboardingLesson,
  type TeachingEligibility,
  type TeachingSnapshot,
} from '../models'
import { currentObjective, isObjectiveClaimable, objectiveRewardDetails } from '../models/objective'
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
  if (!replayMode.value && ['orientation.weapon', 'orientation.outfit'].includes(lesson.id)) {
    // Preserve completed introductions and legacy cohorts without equipment objectives.
    if (ledger.value['orientation.departure']) return true
    const departure = ORIENTATION_STEPS.find((step) => step.id === 'orientation.departure')
    if (departure && objectiveFor(departure)?.is_completed) return true
    if (objectiveByKey.value.size > 0 && !objectiveFor(lesson)) return true
  }
  // Explicit replay reaches claimed steps; otherwise a claimed objective retires the lesson.
  return !replayMode.value && objectiveFor(lesson)?.is_completed === true
}

const pendingLessons = computed(() => ORIENTATION_STEPS.filter((lesson) => !isHandled(lesson)))
const currentLesson = computed(() => pendingLessons.value[0])
const lessonObjective = computed(() => {
  const lesson = currentLesson.value
  return lesson ? objectiveFor(lesson) : undefined
})
const chapter = computed(() => ORIENTATION_CHAPTERS[currentLesson.value?.chapter ?? 0])
const reward = computed(() => objectiveRewardDetails(lessonObjective.value?.reward ?? ''))
const nextLesson = computed(() => pendingLessons.value[1])

const optedIn = computed(() => !!vaultState.value.created || replayMode.value)
const welcomePending = computed(() => !!vaultState.value.created && !vaultState.value.welcomed)
const active = computed(
  () => !!vaultId.value && !vaultState.value.skipped && optedIn.value && !!currentLesson.value
)
const starterObjectives = computed(() =>
  store.objectives.filter(
    (objective) => objective.vault_id === vaultId.value && objective.category === 'starter'
  )
)
const guideObjective = computed(() => currentObjective(starterObjectives.value))
const readyMilestones = computed(() => starterObjectives.value.filter(isObjectiveClaimable).length)
const orientationComplete = computed(
  () =>
    !!vaultId.value &&
    optedIn.value &&
    !vaultState.value.skipped &&
    !replayMode.value &&
    !currentLesson.value &&
    ORIENTATION_STEPS.some(
      (lesson) => lesson.id === 'orientation.departure' && objectiveFor(lesson)?.is_completed
    )
)
const showHandoff = computed(() => orientationComplete.value && !vaultState.value.handoffDismissed)
const showVaultGuide = computed(
  () => orientationComplete.value && !!vaultState.value.handoffDismissed && !!guideObjective.value
)
const showWelcome = computed(() => active.value && welcomePending.value)
const showLesson = computed(() => active.value && !showWelcome.value && !!currentLesson.value)

const earned = computed(() => {
  const objective = lessonObjective.value
  return !!objective && objective.progress >= objective.total
})
const ready = computed(
  () => !replayMode.value && earned.value && !lessonObjective.value?.is_completed
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
  return lesson ? lesson.eligibility(snapshot.value) : 'unknown'
})
const actionable = computed(() => lessonEligibility.value === 'eligible')
const blockedReason = computed(() => {
  const eligibility = lessonEligibility.value
  return typeof eligibility === 'object' ? eligibility.blocked : undefined
})

const {
  claiming,
  error: claimError,
  claim,
  clearError: clearClaimError,
} = useObjectiveClaim(vaultId)

watch([() => currentLesson.value?.id, () => guideObjective.value?.id, vaultId], () =>
  clearClaimError()
)

watch(
  [currentLesson, () => vaultId.value, () => auth.token],
  () => {
    const lesson = currentLesson.value
    const token = auth.token
    if (!lesson || !vaultId.value || !token) return
    if (lesson.id === 'orientation.housing') {
      if (roomStore.availableRooms.length === 0) {
        void roomStore.fetchBuildableRooms(vaultId.value)
      }
      if (roomStore.roomsLoadedVaultId !== vaultId.value) {
        void roomStore.fetchRooms(vaultId.value)
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
  // Re-measure once the ref settles so a target chosen on scroll/resize is ready
  // in the same frame as the cut-out that depends on its bounds.
  void nextTick(() => updateBounds())
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

const { top, left, width, height, update: updateBounds } = useElementBounding(targetEl)
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

// Keep the card opposite the target; only an explicit player action collapses it.
const anchorBelowFold = computed(() => {
  if (!viewportHeight.value || height.value <= 0) return false
  return top.value + height.value / 2 > viewportHeight.value / 2
})
const cardPlacement = computed(() => (anchorBelowFold.value ? 'top' : 'bottom'))

// A manual toggle wins until the lesson changes; data refreshes never reopen or
// re-collapse the card or move focus.
const userCollapsed = ref(false)
const collapsed = computed(() => userCollapsed.value)
const cardClass = computed(() => [
  'onboarding-card fixed inset-x-4 bottom-4 z-[61] mx-auto flex max-h-[calc(100svh-2rem)] max-w-[26rem] flex-col gap-3 overflow-y-auto rounded-lg border border-theme-primary bg-surface-raised p-4 font-mono text-theme-primary shadow-lg sm:right-6 sm:bottom-6 sm:left-auto sm:mx-0 sm:w-96',
  `onboarding-card--${cardPlacement.value}`,
  { 'top-4 bottom-auto sm:top-6 sm:bottom-auto': anchorBelowFold.value },
  { 'onboarding-card--collapsed': collapsed.value },
])
const toggleCollapsed = () => {
  userCollapsed.value = !collapsed.value
}
watch(
  () => currentLesson.value?.id,
  () => {
    userCollapsed.value = false
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
const showScrollToControl = computed(() => !!presentAnchorEl.value && targetEl.value === null)
const scrollToControl = () => {
  presentAnchorEl.value?.scrollIntoView({
    behavior: reducedMotion.value === 'reduce' ? 'auto' : 'smooth',
    block: 'center',
  })
  // Re-resolve now so the spotlight is restored even if the programmatic scroll
  // raises no scroll event (or the element was already inside the viewport).
  refreshViewport()
}
const showNavigate = computed(() => {
  const path = navPath.value
  if (!path || route.path === path || showScrollToControl.value) return false
  const anchor = presentAnchorEl.value?.dataset.onboarding
  if (anchor && !anchor.startsWith('nav-')) return false
  return !currentLesson.value?.route || !route.path.startsWith(`${path}/`)
})
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

function onGuideClaim() {
  const objective = guideObjective.value
  if (!objective || !isObjectiveClaimable(objective)) return
  void claim(objective.id, (claimed) => {
    claimedObjective.value = claimed
  })
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
        }"
        :style="cutoutStyle"
        aria-hidden="true"
      />
      <Card
        v-if="!blockedByOverlay"
        :class="[cardClass, { 'max-h-[calc(50svh-6rem)]': !showWelcome && targetEl }]"
        v-bind="{ role: 'region', 'aria-live': 'polite', 'aria-label': 'Vault onboarding' }"
      >
        <CardHeader class="shrink-0 gap-2 p-0">
          <div class="flex items-center justify-between gap-3">
            <p class="text-[0.65rem] font-bold tracking-[0.14em] text-theme-accent">
              VAULT FIELD GUIDE
            </p>
            <Button
              v-if="!showWelcome"
              variant="ghost"
              size="sm"
              class="onboarding-collapse h-auto px-1 py-0 text-xs"
              :aria-expanded="!collapsed"
              aria-controls="onboarding-guide-body"
              :aria-label="collapsed ? 'Expand guide' : 'Collapse guide'"
              @click="toggleCollapsed"
              >{{ collapsed ? 'Expand' : 'Collapse' }}</Button
            >
          </div>
          <ol
            v-if="!collapsed"
            aria-label="Introduction milestones"
            class="grid grid-cols-4 gap-2 border-y border-theme-primary/20 py-2"
          >
            <li
              v-for="(milestone, index) in ORIENTATION_CHAPTERS"
              :key="milestone.title"
              :aria-current="!showWelcome && currentLesson?.chapter === index ? 'step' : undefined"
              class="flex flex-col gap-1 text-[0.65rem] leading-tight"
              :class="
                index === currentLesson?.chapter ? 'text-theme-primary' : 'text-muted-foreground'
              "
            >
              <span class="font-bold tabular-nums" aria-hidden="true">0{{ index + 1 }}</span>
              <span>{{ milestone.title }}</span>
            </li>
          </ol>
          <CardTitle class="onboarding-title text-base font-bold">
            <h2>{{ showWelcome ? 'Welcome, Overseer' : currentLesson?.title }}</h2>
          </CardTitle>
          <CardDescription v-if="showWelcome" class="text-xs leading-relaxed">
            Your crew is already at work. Your next chapter starts here: meet the crew, welcome a
            newcomer, prepare an explorer and send them into the wasteland.
          </CardDescription>
        </CardHeader>
        <CardContent v-if="showWelcome" class="onboarding-actions flex flex-wrap gap-2 p-0">
          <Button size="sm" @click="start">Start</Button>
          <Button size="sm" variant="ghost" @click="skipTourAction">Skip tour</Button>
        </CardContent>
        <CardContent
          v-else-if="currentLesson"
          v-show="!collapsed"
          v-bind="{ id: 'onboarding-guide-body' }"
          class="flex min-h-0 flex-col gap-3 p-0"
        >
          <div class="min-h-0 space-y-3 overflow-y-auto">
            <p class="text-xs leading-relaxed text-muted-foreground">{{ currentLesson.body }}</p>
            <div
              v-if="lessonObjective && !replayMode"
              class="flex items-start justify-between gap-3 rounded border border-theme-primary/20 bg-theme-primary/5 p-2 text-xs"
            >
              <div>
                <p class="font-bold text-theme-accent">
                  {{
                    lessonObjective.is_completed
                      ? 'REWARD CLAIMED'
                      : ready
                        ? 'READY TO CLAIM'
                        : 'MILESTONE REWARD'
                  }}
                </p>
                <p class="mt-1">
                  {{ reward.kind === 'dweller' ? `${reward.name} joins your vault` : reward.name }}
                </p>
              </div>
              <p
                class="shrink-0 font-bold tabular-nums"
                :aria-label="`Progress: ${lessonObjective.progress} of ${lessonObjective.total}`"
              >
                {{ lessonObjective.progress }} / {{ lessonObjective.total }}
              </p>
            </div>
            <Alert v-if="loadFailed" class="onboarding-note text-xs"
              >Could not refresh the guide. Retry.</Alert
            >
            <Alert v-if="blockedReason" class="onboarding-note text-xs">{{ blockedReason }}</Alert>
            <Alert v-if="claimError" variant="destructive" class="onboarding-error text-xs">{{
              claimError
            }}</Alert>
            <div class="border-t border-theme-primary/20 pt-2 text-xs text-muted-foreground">
              <p>{{ chapter?.outcome }}</p>
              <p v-if="nextLesson" class="mt-1">Next: {{ nextLesson.title }}</p>
              <p v-else class="mt-1">Next: keep building while your explorer travels.</p>
            </div>
          </div>
          <div class="onboarding-actions flex shrink-0 flex-wrap gap-2">
            <Button v-if="ready" size="sm" :disabled="claiming" @click="onClaim">
              {{ claiming ? 'Claiming…' : `Claim ${reward.name}` }}
            </Button>
            <Button v-else-if="showContinue" size="sm" :disabled="claiming" @click="continueLesson"
              >Continue</Button
            >
            <Button
              v-if="showScrollToControl"
              size="sm"
              variant="outline"
              :disabled="claiming"
              @click="scrollToControl"
              >Show control</Button
            >
            <Button
              v-if="showNavigate"
              size="sm"
              variant="outline"
              :disabled="claiming"
              @click="navigateToLesson"
              >{{ navLabel }}</Button
            >
            <Button
              v-if="loadFailed"
              size="sm"
              variant="outline"
              :disabled="claiming"
              @click="refresh"
              >Retry</Button
            >
          </div>
          <div
            class="onboarding-actions flex shrink-0 flex-wrap gap-2 border-t border-theme-primary/20 pt-2"
          >
            <Button size="sm" variant="ghost" :disabled="claiming" @click="skipStepAction"
              >Skip step</Button
            >
            <Button size="sm" variant="ghost" :disabled="claiming" @click="skipTourAction"
              >Skip tour</Button
            >
          </div>
        </CardContent>
      </Card>
    </template>
    <IntroHandoffCard
      v-if="(showHandoff || showVaultGuide) && vaultId"
      v-show="!blockedByOverlay"
      :key="vaultId"
      ref="handoffCard"
      :vault-id="vaultId"
      :compact="!!vaultState.handoffDismissed"
      :milestone="guideObjective"
      :ready-count="readyMilestones"
      :claiming="claiming"
      :claim-error="claimError"
      :class="cardClass"
      @dismiss="patch(vaultId, { handoffDismissed: true })"
      @claim="onGuideClaim"
      @hide="skipTourAction"
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

@media (prefers-reduced-motion: reduce) {
  .onboarding-cutout {
    animation: none;
  }
}
</style>
