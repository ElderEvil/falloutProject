<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { RoomRushResourceGain, RoomRushResult } from '../models/room'
import { rushConsequenceTags } from '../utils/roomRush'

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
const summary = computed(() => {
  const result = props.result
  if (!result) return ''
  if (result.outcome === 'failure') {
    const [incident] = rushConsequenceTags(result.incident_type ? [result.incident_type] : [])
    const parts = [incident ?? 'INCIDENT']
    if (result.happiness_delta !== 0) {
      parts.push(`−${Math.abs(result.happiness_delta)} HAPPINESS`)
    }
    return parts.join(' · ')
  }
  const parts = (Object.entries(result.payout) as [PayoutKey, number][])
    .filter(([, amount]) => amount > 0)
    .map(([key, amount]) => `+${amount} ${PAYOUT_LABELS[key]}`)
  if (result.caps > 0) parts.push(`+${result.caps} CAPS`)
  return parts.join(' · ') || 'COLLECTED'
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
        <strong class="rush-popup__title">{{ success ? 'RUSH OK' : 'RUSH FAIL' }}</strong>
        <p class="rush-popup__message">{{ summary }}</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.rush-feedback {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.rush-flash {
  position: absolute;
  inset: 0;
  animation: rush-flash 700ms ease-out forwards;
}

.rush-flash--success {
  background: radial-gradient(
    circle at center,
    color-mix(in srgb, var(--color-success) 38%, transparent),
    transparent 68%
  );
}

.rush-flash--failure {
  background: radial-gradient(
    circle at center,
    color-mix(in srgb, var(--color-danger) 42%, transparent),
    transparent 68%
  );
}

.rush-popup {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  max-width: min(26rem, calc(100vw - 2rem));
  padding: 1rem 1.5rem 1.1rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  background: color-mix(in srgb, var(--color-surface-sunken) 94%, transparent);
  box-shadow: 0 0 32px color-mix(in srgb, var(--color-theme-primary) 24%, transparent);
  text-align: center;
  animation: rush-popup-in 280ms ease-out;
}

.rush-popup--success {
  border-color: var(--color-success);
}

.rush-popup--failure {
  border-color: var(--color-danger);
}

.rush-popup__sprite {
  width: 13rem;
  height: 11rem;
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
  animation: rush-sprite-pop 420ms cubic-bezier(0.2, 1.4, 0.4, 1) both;
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

@keyframes rush-sprite-pop {
  from {
    opacity: 0;
    transform: scale(0.82) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@media (max-width: 640px) {
  .rush-popup {
    padding: 0.75rem 1rem 0.9rem;
  }

  .rush-popup__sprite {
    width: 10rem;
    height: 8.5rem;
  }

  .rush-popup__title {
    font-size: 1.1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .rush-flash {
    display: none;
  }

  .rush-popup,
  .rush-popup__sprite {
    animation: none;
  }
}
</style>
