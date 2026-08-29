<script setup lang="ts">
/**
 * RewardCard — single reward entry inside a rewards grid.
 *
 * Renders a circular icon container with a color variant, a label, and a
 * value. Variants map to shared color themes (experience, caps, distance,
 * enemies, events) or default to the theme accent.
 */
import { Icon } from '@iconify/vue'

withDefaults(
  defineProps<{
    icon: string
    label: string
    value: string
    variant?: 'experience' | 'caps' | 'distance' | 'enemies' | 'events'
    span?: boolean
  }>(),
  { variant: undefined, span: false }
)
</script>

<template>
  <div class="reward-card" :class="{ span: span }">
    <div class="reward-icon-container" :class="variant">
      <Icon :icon="icon" class="reward-icon" />
    </div>
    <div class="reward-details">
      <div class="reward-label">{{ label }}</div>
      <div class="reward-value" :class="variant ? `${variant}-value` : ''">{{ value }}</div>
    </div>
  </div>
</template>

<style scoped>
.reward-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: color-mix(in srgb, var(--color-theme-primary) 3%, transparent);
  border: 2px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.reward-card:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  border-color: color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  transform: translateY(-2px);
}

.reward-card.span {
  grid-column: 1 / -1;
}

.reward-icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  flex-shrink: 0;
  border: 2px solid var(--color-theme-accent);
  background: color-mix(in srgb, var(--color-theme-secondary) 60%, transparent);
}

.reward-icon-container.experience {
  background: rgba(255, 215, 0, 0.2);
  border-color: var(--color-rarity-legendary);
}

.reward-icon-container.caps {
  background: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border-color: var(--color-theme-primary);
}

.reward-icon-container.distance {
  background: rgba(65, 105, 225, 0.2);
  border-color: var(--color-rarity-rare);
}

.reward-icon-container.enemies {
  background: rgba(255, 0, 0, 0.2);
  border-color: var(--color-danger);
}

.reward-icon-container.events {
  background: rgba(255, 165, 0, 0.2);
  border-color: var(--color-warning);
}

.reward-icon {
  width: 1.9rem;
  height: 1.9rem;
  color: var(--color-theme-accent);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.reward-icon-container.experience .reward-icon {
  color: var(--color-rarity-legendary);
}

.reward-icon-container.caps .reward-icon {
  color: var(--color-theme-primary);
}

.reward-icon-container.distance .reward-icon {
  color: var(--color-rarity-rare);
}

.reward-icon-container.enemies .reward-icon {
  color: var(--color-danger);
}

.reward-icon-container.events .reward-icon {
  color: var(--color-warning);
}

.reward-details {
  flex: 1;
  min-width: 0;
}

.reward-label {
  font-size: 0.75rem;
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.reward-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.experience-value {
  color: var(--color-rarity-legendary);
  text-shadow: 0 0 8px rgba(255, 215, 0, 0.6);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
}

@media (prefers-reduced-motion: reduce) {
  .reward-card {
    transition: none;
  }

  .reward-card:hover {
    transform: none;
  }

  .experience-value {
    animation: none;
  }
}
</style>
