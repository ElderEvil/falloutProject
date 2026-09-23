<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { onClickOutside } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import {
  happinessService,
  type HappinessModifiers,
} from '@/modules/dwellers/services/happinessService'

interface Props {
  dwellerId: string
}

const props = defineProps<Props>()

const showModifiers = ref(false)
const popoverRoot = ref<HTMLElement | null>(null)

onClickOutside(popoverRoot, () => {
  showModifiers.value = false
})

const happinessModifiers = ref<HappinessModifiers | null>(null)
const { run: runLoadModifiers, isLoading: loadingModifiers } = useAsyncAction(
  (dwellerId: string) => happinessService.getDwellerModifiers(dwellerId),
  { context: 'Failed to load happiness modifiers' }
)

const loadHappinessModifiers = async () => {
  if (happinessModifiers.value) {
    showModifiers.value = !showModifiers.value
    return
  }

  const response = await runLoadModifiers(props.dwellerId)
  if (response) {
    happinessModifiers.value = response.data
    showModifiers.value = true
  }
}
</script>

<template>
  <div ref="popoverRoot">
    <TooltipProvider :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="ghost"
            size="sm"
            @click="loadHappinessModifiers"
            :disabled="loadingModifiers"
            aria-label="View happiness modifiers"
          >
            <Icon
              :icon="loadingModifiers ? 'mdi:loading' : 'mdi:information-outline'"
              :class="{ 'animate-spin': loadingModifiers }"
              class="h-4 w-4"
            />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">View happiness modifiers</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <div v-if="showModifiers && happinessModifiers" class="happiness-modifiers">
      <div class="modifiers-header">
        <span class="modifiers-title">Happiness Modifiers</span>
        <Button
          variant="ghost"
          size="sm"
          @click="showModifiers = false"
          aria-label="Close happiness modifiers"
        >
          <Icon icon="mdi:close" class="h-4 w-4" />
        </Button>
      </div>

      <div v-if="happinessModifiers.positive.length > 0" class="modifiers-section">
        <div class="modifiers-label positive">Positive Effects</div>
        <div
          v-for="(modifier, index) in happinessModifiers.positive"
          :key="`pos-${index}`"
          class="modifier-item positive"
        >
          <Icon icon="mdi:arrow-up" class="modifier-icon" />
          <span class="modifier-name">{{ modifier.name }}</span>
          <span class="modifier-value">+{{ modifier.value.toFixed(1) }}</span>
        </div>
      </div>

      <div v-if="happinessModifiers.negative.length > 0" class="modifiers-section">
        <div class="modifiers-label negative">Negative Effects</div>
        <div
          v-for="(modifier, index) in happinessModifiers.negative"
          :key="`neg-${index}`"
          class="modifier-item negative"
        >
          <Icon icon="mdi:arrow-down" class="modifier-icon" />
          <span class="modifier-name">{{ modifier.name }}</span>
          <span class="modifier-value">{{ modifier.value.toFixed(1) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Floating readout: stays fully opaque so the card's bars and labels cannot
   bleed through, but uses the same flat surface + faint border as the app's
   other floating panels instead of a textured acrylic sheen. */
.happiness-modifiers {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 10;
  min-width: 220px;
  background: var(--color-surface-canvas);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border-radius: 6px;
  padding: 0.75rem;
  margin-top: 0.5rem;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6);
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modifiers-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.modifiers-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.modifiers-section {
  margin-top: 0.5rem;
}

.modifiers-section:first-of-type {
  margin-top: 0;
}

.modifiers-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  display: block;
}

.modifiers-label.positive {
  color: var(--color-terminal-green-dark);
}

.modifiers-label.negative {
  color: var(--color-danger);
}

.modifier-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  margin-bottom: 0.25rem;
  background: var(--color-surface-raised);
  border-radius: 4px;
  font-size: 0.8125rem;
  transition: all 0.2s;
}

.modifier-item:hover {
  background: var(--color-surface-hover);
  transform: translateX(2px);
}

.modifier-item.positive {
  border-left: 2px solid var(--color-terminal-green-dark);
}

.modifier-item.negative {
  border-left: 2px solid var(--color-danger);
}

.modifier-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-icon {
  color: var(--color-terminal-green-dark);
}

.modifier-item.negative .modifier-icon {
  color: var(--color-danger);
}

.modifier-name {
  flex: 1;
  color: var(--color-gray-200);
}

.modifier-value {
  font-weight: 600;
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-value {
  color: var(--color-terminal-green-dark);
}

.modifier-item.negative .modifier-value {
  color: var(--color-danger);
}
</style>
