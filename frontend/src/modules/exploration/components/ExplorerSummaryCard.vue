<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { normalizeImageUrl } from '@/core/utils/image'

defineProps<{
  dwellerName: string
  dwellerImageUrl?: string | null
  dwellerLevel: number
  health: number
  maxHealth: number
  progressPercentage: number
  timeRemaining: string
  explorationDuration: number
}>()
</script>

<template>
  <div
    class="mb-4 rounded-lg border-2 border-theme-primary bg-terminal-background p-4 shadow-[0_0_20px_var(--color-theme-glow)]"
  >
    <!-- Dweller Portrait Card -->
    <div
      class="mb-4 flex gap-4 border-b-2 border-theme-primary/30 pb-4 max-md:flex-col max-md:items-center max-md:text-center"
    >
      <div
        class="relative flex h-[70px] w-[70px] shrink-0 items-center justify-center rounded-md border-2 border-theme-primary bg-terminal-background shadow-[0_0_15px_var(--color-theme-glow)]"
      >
        <img
          v-if="dwellerImageUrl"
          :src="normalizeImageUrl(dwellerImageUrl)"
          :alt="`${dwellerName} portrait`"
          class="dweller-portrait h-full w-full rounded-md object-cover"
        />
        <Icon
          v-else
          icon="mdi:account"
          class="h-[45px] w-[45px] text-theme-primary drop-shadow-[0_0_8px_var(--color-theme-glow)]"
        />
        <div
          class="absolute -bottom-1.5 -right-1.5 rounded-[3px] bg-theme-primary px-2 py-1 text-xs font-bold text-black shadow-[0_0_10px_var(--color-theme-glow)]"
        >
          LVL {{ dwellerLevel }}
        </div>
      </div>
      <div class="flex flex-1 flex-col justify-center">
        <h2
          class="mb-2 text-xl font-bold text-theme-primary [text-shadow:0_0_10px_var(--color-theme-glow)] max-md:text-2xl"
        >
          {{ dwellerName }}
        </h2>
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <span class="min-w-[50px] text-xs text-theme-primary/80">Health</span>
            <div
              class="exploration-meter exploration-meter--health rounded-full"
              role="progressbar"
              aria-label="Health"
              :aria-valuenow="health"
              aria-valuemin="0"
              :aria-valuemax="maxHealth"
            >
              <div
                class="exploration-meter__fill rounded-full"
                :style="{
                  width: `${(health / maxHealth) * 100}%`,
                }"
              ></div>
              <div class="exploration-meter__segments" aria-hidden="true"></div>
            </div>
            <span class="min-w-[60px] text-right text-xs font-bold text-theme-primary"
              >{{ health }}/{{ maxHealth }}</span
            >
          </div>
        </div>
      </div>
    </div>

    <!-- Progress Section -->
    <div class="mb-4">
      <h3
        class="mb-2 flex items-center text-base font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
      >
        <Icon icon="mdi:compass" class="mr-2" />
        Exploring Wasteland - {{ explorationDuration }}h
      </h3>
      <div
        class="exploration-meter exploration-meter--progress mb-2 rounded-full"
        role="progressbar"
        aria-label="Exploration progress"
        :aria-valuenow="progressPercentage"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <div
          class="exploration-meter__fill rounded-full"
          :style="{ width: `${progressPercentage}%` }"
        ></div>
        <div class="exploration-meter__segments" aria-hidden="true"></div>
      </div>
      <div class="flex justify-between text-sm font-bold">
        <span class="text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]"
          >{{ Math.round(progressPercentage) }}% Complete</span
        >
        <span class="text-theme-primary/80">{{ timeRemaining }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.exploration-meter {
  position: relative;
  display: block;
  flex: 1;
  overflow: hidden;
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.65);
  background: rgb(0 0 0 / 0.7);
  box-shadow: inset 0 0 8px rgb(0 0 0 / 0.9);
}

.exploration-meter--health {
  height: 0.75rem;
}

.exploration-meter--progress {
  height: 1.25rem;
}

.exploration-meter__fill {
  height: 100%;
  background: var(--color-theme-primary);
  box-shadow: inset 0 0 5px rgb(255 255 255 / 0.28), 0 0 8px var(--color-theme-glow);
  transition: width 0.5s ease;
}

.exploration-meter__segments {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    90deg,
    transparent 0,
    transparent calc(12.5% - 1px),
    rgb(0 0 0 / 0.5) calc(12.5% - 1px),
    rgb(0 0 0 / 0.5) 12.5%
  );
}
</style>
