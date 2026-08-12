<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Exploration } from '../stores/exploration'

defineProps<{
  exploration: Exploration
}>()
</script>

<template>
  <div class="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:map-marker-distance"
        class="mb-1 h-7 w-7 text-theme-primary [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.total_distance }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Miles</div>
      </div>
    </div>
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:treasure-chest"
        class="mb-1 h-7 w-7 text-theme-primary [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.loot_collected?.length || 0 }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Items</div>
      </div>
    </div>
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:currency-usd"
        class="mb-1 h-7 w-7 text-[#ffd700] [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.total_caps_found }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Caps</div>
      </div>
    </div>
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:medical-bag"
        class="mb-1 h-7 w-7 text-[#4caf50] [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.stimpaks || 0 }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">
          Stimpaks
        </div>
      </div>
    </div>
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:pill"
        class="mb-1 h-7 w-7 text-[#ffeb3b] [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.radaways || 0 }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">RadAway</div>
      </div>
    </div>
    <div
      class="flex flex-col items-center rounded-md border border-theme-primary/30 bg-terminal-background p-2 text-center transition duration-[var(--transition-base)] hover:-translate-y-px hover:border-theme-primary hover:shadow-[0_0_12px_var(--color-theme-glow)]"
    >
      <Icon
        icon="mdi:skull"
        class="mb-1 h-7 w-7 text-[#ff4444] [filter:drop-shadow(0_0_6px_var(--color-theme-glow))]"
      />
      <div class="text-center">
        <div
          class="text-xl font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
        >
          {{ exploration.enemies_encountered }}
        </div>
        <div class="text-[0.625rem] uppercase tracking-[0.05em] text-theme-primary/70">Enemies</div>
      </div>
    </div>
  </div>
</template>
