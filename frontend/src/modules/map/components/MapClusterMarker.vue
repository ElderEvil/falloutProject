<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  x: number
  y: number
  /** Number of individual markers collapsed into this badge. */
  count: number
  scale?: number
  /** At least one member is an unseen discovery — keep the discovery pulse. */
  unseen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  unseen: false,
  scale: 1,
})

const emit = defineEmits<{
  (e: 'click'): void
}>()

const tooltipText = computed(() => `Zoom in — ${props.count} nearby discoveries`)

function handleClick() {
  emit('click')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    emit('click')
  }
}
</script>

<template>
  <g
    :transform="`translate(${x}, ${y})${scale === 1 ? '' : ` scale(${scale})`}`"
    class="map-cluster"
    :class="{ 'cluster-unseen': unseen }"
    role="button"
    tabindex="0"
    :aria-label="tooltipText"
    @click="handleClick"
    @keydown="handleKeydown"
  >
    <circle class="cluster-hit-area" r="6" fill="transparent" />
    <title>{{ tooltipText }}</title>
    <!-- Dark knockout disc + accent ring: the aggregate reads as one target and
         stays legible over any terrain, matching the individual markers. -->
    <circle class="cluster-backing" r="3.6" />
    <circle class="cluster-ring" r="3.6" />
    <text
      class="cluster-count"
      x="0"
      y="0"
      text-anchor="middle"
      dominant-baseline="central"
      aria-hidden="true"
      >×{{ count }}</text
    >
  </g>
</template>

<style scoped>
.map-cluster {
  cursor: pointer;
  transition: transform 150ms ease;
}

.map-cluster:hover,
.map-cluster:focus-visible {
  filter: drop-shadow(0 0 6px var(--color-theme-primary));
}

.map-cluster:focus,
.map-cluster:focus-visible {
  outline: none;
}

.cluster-hit-area {
  fill: transparent;
}

.cluster-backing {
  fill: color-mix(in srgb, var(--color-terminal-background) 90%, transparent);
  pointer-events: none;
}

.cluster-ring {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.35;
  opacity: 0.85;
  pointer-events: none;
}

.cluster-count {
  fill: var(--color-theme-primary);
  font-family: var(--font-family-mono);
  font-size: 2.7px;
  letter-spacing: -0.04em;
  pointer-events: none;
}

/* An unseen discovery hides inside the cluster: pulse the ring/count so the
   aggregate still advertises there is something new to look at. */
.cluster-unseen .cluster-ring,
.cluster-unseen .cluster-count {
  animation: cluster-pulse 2s ease-in-out infinite;
}

@keyframes cluster-pulse {
  0%,
  100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cluster-unseen .cluster-ring,
  .cluster-unseen .cluster-count {
    animation: none;
  }
}
</style>
