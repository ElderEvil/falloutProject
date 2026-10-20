<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'

const props = withDefaults(
  defineProps<{
    icon?: string
    monogram?: string
    marker?: { icon?: string; monogram?: string; label: string }
    color: string
    label: string
    category?: string
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { showLabel: true, size: 'md' }
)

/** Icon-only badges carry no text, so the accessible name must state the category too. */
const accessibleName = computed(() =>
  [props.category ? `${props.category}: ${props.label}` : props.label, props.marker?.label]
    .filter(Boolean)
    .join(' · ')
)
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <Tooltip>
      <TooltipTrigger as-child>
        <span
          class="dweller-badge"
          :class="[`size-${size}`, { 'icon-only': !showLabel, 'has-state-marker': marker }]"
          :style="{ '--badge-color': color }"
          :aria-label="accessibleName"
          role="img"
        >
          <Icon v-if="icon" :icon="icon" class="badge-icon" :ariaHidden="true" />
          <span v-else-if="monogram" class="badge-monogram" aria-hidden="true">{{ monogram }}</span>
          <span v-if="marker" class="badge-state-marker" aria-hidden="true">
            <Icon v-if="marker.icon" :icon="marker.icon" />
            <span v-else>{{ marker.monogram }}</span>
          </span>
          <span v-if="showLabel" class="badge-label">{{ label }}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="top">{{ accessibleName }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>

<style scoped>
/* Informational badge (badge-info intent): color codes the category, but a fact
   never glows, never animates, and never responds to hover — that vocabulary is
   reserved for actions and live status. */
.dweller-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid var(--badge-color);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
  color: var(--badge-color);
  white-space: nowrap;
}

.size-sm {
  padding: 0.15rem 0.4rem;
  font-size: 0.7rem;
}

.icon-only {
  justify-content: center;
  padding: 0;
}

.icon-only.size-sm {
  width: 1.5rem;
  height: 1.5rem;
}

.icon-only.size-sm.has-state-marker {
  width: 2.5rem;
  gap: 0.15rem;
}

.icon-only.size-md {
  width: 2.25rem;
  height: 2.25rem;
}

.icon-only.size-md.has-state-marker {
  width: 3rem;
  gap: 0.2rem;
}

.size-md {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.badge-icon {
  font-size: 1.25em;
}

.badge-monogram {
  font-weight: 700;
  line-height: 1;
}

.badge-state-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1em;
  border-left: 1px solid currentcolor;
  padding-left: 0.3rem;
  font-size: 0.85em;
  font-weight: 700;
  line-height: 1;
}

.badge-label {
  font-weight: 700;
  text-transform: capitalize;
}
</style>
