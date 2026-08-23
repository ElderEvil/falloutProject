<script setup lang="ts">
import { computed } from 'vue'
import type { ArenaFighter, ArenaRosterEntry } from '../api/arena'

interface Props {
  side: 'A' | 'B'
  fighter: ArenaFighter | null
  canChange: boolean
  damageNumbers: Array<{ id: number; amount: number }>
  options: ArenaRosterEntry[]
  pickerOpen: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  clear: [side: 'A' | 'B']
  togglePicker: [side: 'A' | 'B']
  select: [side: 'A' | 'B', entry: ArenaRosterEntry]
}>()

const powerLabel = computed(() => (props.fighter ? Math.round(props.fighter.power) : 0))

const healthPercent = (f: ArenaFighter | null) =>
  f ? Math.round((f.health / Math.max(1, f.max_health)) * 100) : 0
</script>

<template>
  <div class="fighter-slot">
    <div v-if="fighter" class="fighter-card">
      <button v-if="canChange" class="slot-clear" type="button" aria-label="Clear fighter" @click="emit('clear', side)">✕</button>
      <div class="damage-layer">
        <span v-for="d in damageNumbers" :key="d.id" class="damage-number">-{{ d.amount }}</span>
      </div>
      <div class="fighter-portrait">{{ fighter.name[0] }}</div>
      <div class="fighter-name">{{ fighter.name }}</div>
      <div class="fighter-meta">Lv {{ fighter.level }} &middot; POW {{ powerLabel }}</div>
      <div class="hp-track">
        <div class="hp-fill" :style="{ width: `${healthPercent(fighter)}%` }"></div>
      </div>
      <div class="hp-text">{{ fighter.health }}/{{ fighter.max_health }}</div>
      <button v-if="canChange" class="slot-swap" type="button" @click="emit('togglePicker', side)">SWAP</button>
    </div>
    <button v-else class="fighter-slot-empty" type="button" @click="emit('togglePicker', side)">
      <span>+ PICK FIGHTER</span>
    </button>
    <div v-if="pickerOpen && canChange" class="picker">
      <button v-for="entry in options" :key="entry.id" class="picker-option" type="button" @click="emit('select', side, entry)">
        <span class="picker-name">{{ entry.name }}</span>
        <span class="picker-meta">Lv {{ entry.level }} &middot; {{ entry.health }} HP</span>
      </button>
      <div v-if="!options.length" class="picker-empty">No available adults &mdash; assign dwellers to the Arena first.</div>
    </div>
  </div>
</template>

<style scoped>
.fighter-slot {
  position: relative;
  display: flex;
  flex-direction: column;
}

.slot-clear {
  position: absolute;
  top: 4px;
  right: 6px;
  z-index: 3;
  border: none;
  background: transparent;
  color: var(--color-gray-500);
  font-size: 0.8rem;
  cursor: pointer;
}

.slot-clear:hover {
  color: var(--color-danger);
}

.slot-swap {
  margin-top: 0.35rem;
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  background: transparent;
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  cursor: pointer;
}

.fighter-slot-empty {
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

.fighter-slot-empty:hover {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
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
  color: var(--color-theme-primary);
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

.fighter-card {
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

.fighter-card.vacant {
  opacity: 0.5;
}

.fighter-portrait {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 2px solid var(--color-theme-primary);
  background: var(--color-surface-raised);
  color: var(--color-theme-primary);
  font-size: 1.5rem;
  font-weight: bold;
}

.fighter-name {
  font-weight: 600;
  color: var(--color-theme-primary);
  text-align: center;
}

.fighter-meta {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}

.hp-track {
  width: 100%;
  height: 10px;
  background: var(--color-surface-canvas);
  border: 1px solid var(--color-surface-hover);
  border-radius: 9999px;
  overflow: hidden;
}

.hp-fill {
  height: 100%;
  background: var(--color-theme-primary);
  transition: width 0.5s ease;
}

.hp-text {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}
</style>
