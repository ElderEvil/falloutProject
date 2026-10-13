<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import type { ArenaCreature } from '../api/arena'
import type { ArenaCreatureView } from '../models/arena'

interface Props {
  creature: ArenaCreatureView | null
  canChange: boolean
  damageNumbers: Array<{ id: number; amount: number }>
  options: ArenaCreature[]
  pickerOpen: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  clear: [key: string]
  togglePicker: []
  select: [creature: ArenaCreature]
}>()

const powerLabel = computed(() => (props.creature ? Math.round(props.creature.power) : null))

const healthPercent = (creature: ArenaCreatureView | null) =>
  creature ? Math.round((creature.health / Math.max(1, creature.max_health)) * 100) : 0
</script>

<template>
  <div class="creature-slot">
    <div v-if="creature" class="creature-card">
      <TooltipProvider v-if="canChange" :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button
              class="slot-clear"
              size="icon-sm"
              variant="ghost"
              :aria-label="`Clear ${creature.name}`"
              @click="emit('clear', creature.key)"
            >
              <Icon icon="mdi:close" class="h-4 w-4 text-danger" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Clear creature</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <div class="damage-layer">
        <span v-for="d in damageNumbers" :key="d.id" class="damage-number">-{{ d.amount }}</span>
      </div>
      <div class="creature-icon">
        <Icon icon="mdi:paw" />
      </div>
      <div class="creature-name">{{ creature.name }}</div>
      <div class="creature-meta">POW {{ powerLabel }}</div>
      <div class="hp-track">
        <Progress :model-value="healthPercent(creature)" class="h-2.5" />
      </div>
      <div class="hp-text">{{ creature.health }}/{{ creature.max_health }}</div>
    </div>
    <button v-else class="creature-slot-empty" type="button" @click="emit('togglePicker')">
      <span>+ ADD CREATURE</span>
    </button>
    <div v-if="pickerOpen && canChange" class="picker">
      <button v-for="option in options" :key="option.key" class="picker-option" type="button" @click="emit('select', option)">
        <span class="picker-name">{{ option.name }}</span>
        <span class="picker-meta">POW {{ Math.round(option.power) }} &middot; {{ option.max_hp }} HP</span>
      </button>
      <div v-if="!options.length" class="picker-empty">No creatures available.</div>
    </div>
  </div>
</template>

<style scoped>
.creature-slot {
  position: relative;
  display: flex;
  flex-direction: column;
}

.slot-clear {
  position: absolute;
  top: 4px;
  right: 6px;
  z-index: 3;
}

.creature-slot-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: 1rem;
  border: 1px dashed var(--color-surface-hover);
  border-radius: 8px;
  background: transparent;
  color: var(--color-gray-500);
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.creature-slot-empty:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.picker {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 10;
  margin-top: 0.25rem;
  max-height: 160px;
  overflow-y: auto;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-surface-hover);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.picker-option {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0.45rem 0.6rem;
  cursor: pointer;
}

.picker-option:hover {
  background: var(--color-surface-hover);
}

.picker-name {
  font-size: 0.8rem;
  color: var(--color-danger);
}

.picker-meta {
  font-size: 0.65rem;
  color: var(--color-gray-400);
}

.picker-empty {
  padding: 0.6rem;
  font-size: 0.7rem;
  color: var(--color-gray-500);
}

.creature-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 1rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 8px;
}

.damage-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.damage-number {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  color: var(--color-danger);
  font-weight: bold;
  font-size: 0.95rem;
  text-shadow: 0 0 8px rgba(255, 0, 0, 0.5);
  animation: damage-float 0.9s ease-out forwards;
  z-index: 2;
}

@keyframes damage-float {
  from {
    opacity: 1;
    transform: translate(-50%, 0);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -32px);
  }
}

.creature-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 2px solid var(--color-danger);
  background: var(--color-surface-raised);
  color: var(--color-danger);
  font-size: 1.75rem;
}

.creature-name {
  font-weight: 600;
  color: var(--color-danger);
  text-align: center;
}

.creature-meta {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}

.hp-track {
  width: 100%;
}

.hp-text {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}
</style>
