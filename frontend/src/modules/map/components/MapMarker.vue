<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

interface Props {
  x: number
  y: number
  name: string
  type: 'home_vault' | 'origin' | 'visited' | 'discovery' | 'vault'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'click'): void
}>()

const typeIcons: Record<string, string> = {
  home_vault: 'mdi:home-city',
  origin: 'mdi:flag',
  visited: 'mdi:eye',
  discovery: 'mdi:compass',
  vault: 'mdi:radioactive',
}

const typeLabels: Record<string, string> = {
  home_vault: 'Home Vault',
  origin: 'Origin',
  visited: 'Visited',
  discovery: 'Discovery',
  vault: 'Vault Signal',
}

const icon = computed(() => typeIcons[props.type] ?? 'mdi:map-marker')
const label = computed(() => typeLabels[props.type] ?? props.type)
const isDiscovery = computed(() => props.type === 'discovery')
const isVault = computed(() => props.type === 'vault')

const tooltipText = computed(() => `${props.name} (${label.value})`)
</script>

<template>
  <g :transform="`translate(${x}, ${y})`" class="map-marker cursor-pointer" @click="emit('click')">
    <UTooltip :text="tooltipText" position="top">
      <foreignObject x="-4" y="-4" width="8" height="8">
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          class="marker-icon"
          :class="{
            'marker-discovery': isDiscovery,
            'marker-vault': isVault,
          }"
        >
          <Icon :icon="icon" class="h-full w-full" />
        </div>
      </foreignObject>
    </UTooltip>
  </g>
</template>

<style scoped>
.map-marker {
  transition: transform 150ms ease;
}

.map-marker:hover {
  filter: drop-shadow(0 0 3px var(--color-theme-primary));
}

.marker-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-theme-primary);
}

.marker-discovery {
  animation: discovery-pulse 2s ease-in-out infinite;
}

.marker-vault {
  color: var(--color-warning);
  opacity: 0.7;
}

@keyframes discovery-pulse {
  0%,
  100% {
    opacity: 0.6;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}
</style>
