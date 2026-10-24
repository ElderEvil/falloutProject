<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { RoomRushResourceGain, RoomRushResult } from '../models/room'

interface Props {
  result: RoomRushResult | null
}

const props = defineProps<Props>()

type PayoutKey = keyof RoomRushResourceGain

const PAYOUT_LABELS: Record<PayoutKey, string> = {
  power: 'POWER',
  food: 'FOOD',
  water: 'WATER',
  stimpack: 'STIMPAKS',
  radaway: 'RADAWAY',
}

const visible = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

const success = computed(() => props.result?.outcome === 'success')
const spriteUrl = computed(() =>
  success.value ? '/assets/vault-boy/rush-ok.webp' : '/assets/vault-boy/rush-fail.webp'
)
const gains = computed(() => {
  if (!props.result) return []
  const rows = (Object.entries(props.result.payout) as [PayoutKey, number][])
    .filter(([, amount]) => amount > 0)
    .map(([key, amount]) => `+${amount} ${PAYOUT_LABELS[key]}`)
  if (props.result.caps > 0) rows.push(`+${props.result.caps} CAPS`)
  if (props.result.outcome === 'failure' && props.result.happiness_delta !== 0) {
    rows.push(`${props.result.happiness_delta} HAPPINESS`)
  }
  if (props.result.incident_type) {
    rows.push(props.result.incident_type.replaceAll('_', ' ').toUpperCase())
  }
  return rows
})

watch(
  () => props.result,
  (result) => {
    if (!result) {
      visible.value = false
      return
    }
    visible.value = true
    if (hideTimer !== null) clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      visible.value = false
    }, 4200)
  },
  { immediate: true }
)

onUnmounted(() => {
  if (hideTimer !== null) clearTimeout(hideTimer)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && result"
      :key="`${result.stacks_after}-${result.outcome}`"
      class="rush-feedback"
      aria-live="assertive"
    >
      <div
        class="rush-flash"
        :class="success ? 'rush-flash--success' : 'rush-flash--failure'"
        aria-hidden="true"
      />
      <div
        class="rush-popup"
        :class="success ? 'rush-popup--success' : 'rush-popup--failure'"
        role="status"
      >
        <div
          class="rush-popup__sprite"
          :style="{ backgroundImage: `url(${spriteUrl})` }"
          aria-hidden="true"
        />
        <div class="rush-popup__copy">
          <strong class="rush-popup__title">{{ success ? 'RUSH OK' : 'RUSH FAIL' }}</strong>
          <p class="rush-popup__message">{{ result.message }}</p>
          <div v-if="gains.length" class="rush-popup__gains">
            <span v-for="gain in gains" :key="gain">{{ gain }}</span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.rush-feedback {
  position: fixed;
  inset: 0;
  z-index: 200;
  pointer-events: none;
}

.rush-flash {
  position: absolute;
  inset: 0;
  animation: rush-flash 700ms ease-out forwards;
}

.rush-flash--success {
  background: radial-gradient(
    circle at 62% 58%,
    color-mix(in srgb, var(--color-success) 38%, transparent),
    transparent 68%
  );
}

.rush-flash--failure {
  background: radial-gradient(
    circle at 62% 58%,
    color-mix(in srgb, var(--color-danger) 42%, transparent),
    transparent 68%
  );
}

.rush-popup {
  position: absolute;
  right: 1.5rem;
  bottom: 1.5rem;
  display: flex;
  align-items: flex-end;
  gap: 0.25rem;
  max-width: min(34rem, calc(100vw - 2rem));
  padding: 0.75rem 1rem 0.75rem 0;
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  background: color-mix(in srgb, var(--color-surface-sunken) 92%, transparent);
  box-shadow: 0 0 28px color-mix(in srgb, var(--color-theme-primary) 24%, transparent);
  animation: rush-popup-in 280ms ease-out;
}

.rush-popup--success {
  border-color: var(--color-success);
}

.rush-popup--failure {
  border-color: var(--color-danger);
}

.rush-popup__sprite {
  flex: 0 0 auto;
  width: 16rem;
  height: 16rem;
  margin: -4.5rem 0 -1.5rem -2rem;
  background-repeat: no-repeat;
  background-position: 0 0;
  background-size: 700% 100%;
  animation: rush-vault-boy 1.05s steps(7, jump-none) forwards;
}

.rush-popup__copy {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-bottom: 0.25rem;
}

.rush-popup__title {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.rush-popup--success .rush-popup__title {
  color: var(--color-success);
}

.rush-popup--failure .rush-popup__title {
  color: var(--color-danger);
}

.rush-popup__message {
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 0.8125rem;
}

.rush-popup__gains {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.rush-popup__gains span {
  padding: 0.1rem 0.35rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 3px;
  color: var(--color-theme-primary);
  font-size: 0.6875rem;
  letter-spacing: 0.04em;
}

@keyframes rush-flash {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

@keyframes rush-popup-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes rush-vault-boy {
  from {
    background-position: 0 0;
  }
  to {
    background-position: 100% 0;
  }
}

@media (max-width: 640px) {
  .rush-popup {
    right: 0.75rem;
    bottom: 0.75rem;
    left: 0.75rem;
    max-width: none;
    padding-right: 0.75rem;
  }

  .rush-popup__sprite {
    width: 11rem;
    height: 11rem;
    margin: -3rem 0 -1rem -1.25rem;
  }

  .rush-popup__title {
    font-size: 1.1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .rush-flash {
    display: none;
  }

  .rush-popup {
    animation: none;
  }

  .rush-popup__sprite {
    animation: none;
    background-position: 0 0;
  }
}
</style>
