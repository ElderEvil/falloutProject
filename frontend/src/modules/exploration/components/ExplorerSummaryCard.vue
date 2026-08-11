<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

defineProps<{
  dwellerName: string
  dwellerLevel: number
  health: number
  maxHealth: number
  progressPercentage: number
  timeRemaining: string
  explorationDuration: number
  dweller: DwellerShort | null
}>()
</script>

<template>
  <div class="mb-4 rounded-lg border-2 border-theme-primary bg-surface-warm-dark p-4 shadow-[0_0_20px_var(--color-theme-glow)]">
    <!-- Dweller Portrait Card -->
    <div class="mb-4 flex gap-4 border-b-2 border-theme-primary/30 pb-4 max-md:flex-col max-md:items-center max-md:text-center">
      <div class="relative flex h-[70px] w-[70px] shrink-0 items-center justify-center rounded-md border-2 border-theme-primary bg-surface-warm-dark shadow-[0_0_15px_var(--color-theme-glow)]">
        <Icon icon="mdi:account" class="h-[45px] w-[45px] text-theme-primary drop-shadow-[0_0_8px_var(--color-theme-glow)]" />
        <div class="absolute -bottom-1.5 -right-1.5 rounded-[3px] bg-theme-primary px-2 py-1 text-xs font-bold text-black shadow-[0_0_10px_var(--color-theme-glow)]">
          LVL {{ dwellerLevel }}
        </div>
      </div>
      <div class="flex flex-1 flex-col justify-center">
        <h2 class="mb-2 text-xl font-bold text-theme-primary [text-shadow:0_0_10px_var(--color-theme-glow)] max-md:text-2xl">{{ dwellerName }}</h2>
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <span class="min-w-[50px] text-xs text-theme-primary/80">Health</span>
            <div class="h-4 flex-1 overflow-hidden rounded-[3px] border border-theme-primary/40 bg-surface-warm-dark">
              <div
                class="h-full bg-gradient-to-r from-theme-primary to-theme-accent shadow-[0_0_12px_var(--color-theme-glow)] transition-[width] duration-300"
                :style="{
                  width: `${(health / maxHealth) * 100}%`,
                }"
              ></div>
            </div>
            <span class="min-w-[60px] text-right text-xs font-bold text-theme-primary">{{ health }}/{{ maxHealth }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Progress Section -->
    <div class="mb-4">
      <h3 class="mb-2 flex items-center text-base font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]">
        <Icon icon="mdi:compass" class="mr-2" />
        Exploring Wasteland - {{ explorationDuration }}h
      </h3>
      <div class="mb-2 h-7 overflow-hidden rounded-md border-2 border-theme-primary bg-surface-warm-dark">
        <div
          class="h-full bg-gradient-to-r from-theme-primary to-theme-accent shadow-[0_0_15px_var(--color-theme-glow)] transition-[width] duration-500"
          :style="{ width: `${progressPercentage}%` }"
        ></div>
      </div>
      <div class="flex justify-between text-sm font-bold">
        <span class="text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]">{{ Math.round(progressPercentage) }}% Complete</span>
        <span class="text-theme-primary/80">{{ timeRemaining }}</span>
      </div>
    </div>
  </div>
</template>
