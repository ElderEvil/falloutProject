<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useElementBounding, usePreferredReducedMotion } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useObjectiveClaim } from '../composables/useObjectiveClaim'
import { useOnboardingState, type OnboardingState } from '@/core/composables/useOnboardingState'
import { currentObjective } from '../models/objective'

/** Orientation chapters own the tour; later chapters guide from the Objectives tab. */
const ORIENTATION_TEMPLATE_KEYS = new Set([
  'starter:assign a dweller correctly',
  'starter:build a living quarters',
  'starter:send a dweller exploring',
])

/** Orientation step → candidate `data-onboarding` anchors, first present wins (see docs/frontend/ONBOARDING.md). */
const STEP_ANCHORS: Record<string, string[]> = {
  'starter:assign a dweller correctly': ['nav-dwellers'],
  'starter:build a living quarters': ['build-living-room', 'build'],
  'starter:send a dweller exploring': ['wasteland'],
}

const store = useObjectivesStore()
const toast = useToast()
const reducedMotion = usePreferredReducedMotion()

const route = useRoute()
const vaultId = computed(() =>
  route.path.startsWith('/vault/') && typeof route.params.id === 'string' ? route.params.id : null
)

const { vaultState: readVaultState, patch } = useOnboardingState()
const vaultState = computed<OnboardingState>(() => readVaultState(vaultId.value))
const patchState = (next: Partial<OnboardingState>) => patch(vaultId.value, next)

const step = computed(() => {
  const current = currentObjective(store.objectives)
  return current?.category === 'starter' ? current : undefined
})
const anchorKeys = computed(() =>
  step.value?.template_key ? (STEP_ANCHORS[step.value.template_key] ?? []) : []
)

const { claiming, claim } = useObjectiveClaim(vaultId)

const active = computed(
  () =>
    !!vaultId.value &&
    !!step.value &&
    !vaultState.value.skipped &&
    ORIENTATION_TEMPLATE_KEYS.has(step.value.template_key ?? '')
)
const atStart = computed(() => step.value?.sequence === 0)
const showWelcome = computed(
  () => active.value && atStart.value && !!vaultState.value.created && !vaultState.value.welcomed
)
const showStep = computed(() => active.value && !showWelcome.value)

const refresh = () => {
  if (vaultId.value && !vaultState.value.skipped) return store.fetchObjectives(vaultId.value)
  return undefined
}
watch([vaultId, () => route.fullPath], () => void refresh(), { immediate: true })
usePolling(refresh, { interval: 30_000, immediate: false })

const targetEl = ref<HTMLElement | null>(null)
const modalOpen = ref(false)

// The shell renders targets asynchronously (nav bar, room cells) and the dim must not
// fight an open modal, so re-resolve on every DOM change rather than once.
function resolveTarget() {
  targetEl.value =
    anchorKeys.value
      .map((key) => document.querySelector<HTMLElement>(`[data-onboarding="${key}"]`))
      .find((element) => element !== null) ?? null
  modalOpen.value = document.querySelector('[role="dialog"]') !== null
}
watch([() => step.value?.template_key, () => step.value?.id], () => resolveTarget(), { flush: 'post' })

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
// A zero-size (hidden) target would leave a tiny hole in the dim, so it gets no cut-out.
const rectReady = computed(() => width.value > 0 && height.value > 0)
const showCutout = computed(() => showStep.value && targetEl.value !== null && rectReady.value)
const cutoutStyle = computed(() => ({
  top: `${top.value - 4}px`,
  left: `${left.value - 4}px`,
  width: `${width.value + 8}px`,
  height: `${height.value + 8}px`,
}))

const ready = computed(() => !!step.value && step.value.progress >= step.value.total)

const start = () => patchState({ welcomed: true })
const skip = () => patchState({ skipped: true })

function onClaim() {
  const current = step.value
  if (!current) return
  void claim(current.id, (claimed) => toast.success(`${claimed.reward} claimed`))
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
          'onboarding-cutout--off': modalOpen,
        }"
        :style="cutoutStyle"
        aria-hidden="true"
      />
      <section
        class="onboarding-card"
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
            <Button size="sm" variant="ghost" @click="skip">Skip tour</Button>
          </div>
        </template>
        <template v-else-if="showStep && step">
          <p class="onboarding-eyebrow">NEXT STEP</p>
          <h2 class="onboarding-title">{{ step.challenge }}</h2>
          <p v-if="step.description" class="onboarding-body">{{ step.description }}</p>
          <p class="onboarding-progress">{{ step.progress }} / {{ step.total }}</p>
          <div class="onboarding-actions">
            <Button v-if="ready" size="sm" :disabled="claiming" @click="onClaim">
              {{ claiming ? 'Claiming…' : `Claim ${step.reward}` }}
            </Button>
            <Button size="sm" variant="ghost" @click="skip">Skip tour</Button>
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

.onboarding-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

@media (prefers-reduced-motion: reduce) {
  .onboarding-cutout {
    animation: none;
  }
}
</style>
