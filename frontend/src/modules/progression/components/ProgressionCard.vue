<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'

/**
 * Shared chrome for the objective and quest cards: the card surface, the accent bar,
 * the title/description block, the completed treatment and its stamp, and the action row.
 *
 * The bodies differ by design — an objective shows one progress bar, a quest shows rewards,
 * requirements, a party and a duration — so they arrive through the default slot, and each
 * card keeps its own props, emits and action behaviour.
 */
interface Props {
  title: string
  description?: string | null
  completed?: boolean
}

withDefaults(defineProps<Props>(), { description: null, completed: false })
</script>

<template>
  <Card class="progression-card" :class="{ 'progression-card--completed': completed }">
    <div class="progression-header">
      <slot name="leading" />
      <h3 class="progression-title">{{ title }}</h3>
      <slot name="badges" />
    </div>

    <p v-if="description" class="progression-description">{{ description }}</p>

    <div class="progression-divider border-t border-theme-primary/20 my-3"></div>

    <slot />

    <div v-if="completed" class="progression-stamp">
      <Icon icon="mdi:check-circle" class="stamp-icon" />
      Completed
    </div>
    <slot v-else name="action" />
  </Card>
</template>

<style scoped>
.progression-card {
  background: var(--color-surface-warm-dark);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.progression-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.progression-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px var(--color-theme-glow);
}

.progression-card--completed {
  border-color: var(--color-quest-muted);
  opacity: 0.75;
}

.progression-card--completed::before {
  background: var(--color-quest-muted);
}

.progression-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.progression-title {
  flex: 1;
  margin: 0;
  font-size: 1.1rem;
  font-weight: bold;
  line-height: 1.25;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.progression-description {
  margin: 0 0 12px;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--color-theme-primary);
  opacity: 0.85;
}

.progression-stamp {
  width: 100%;
  padding: 10px 16px;
  background: color-mix(in srgb, var(--color-theme-primary) 10%, transparent);
  border: 2px dashed var(--color-quest-muted);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-weight: bold;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.stamp-icon {
  font-size: 1.2rem;
}
</style>
