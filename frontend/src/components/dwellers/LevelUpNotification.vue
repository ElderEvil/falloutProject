<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  visible: boolean
  dwellerName: string
  newLevel: number
  hpGain?: number
  totalXP?: number
}

withDefaults(defineProps<Props>(), {
  hpGain: 5,
  totalXP: 0
})
</script>

<template>
  <Transition name="level-up">
    <div v-if="visible" class="level-up-notification">
      <div class="level-up-content">
        <Icon icon="mdi:arrow-up-bold-circle" class="level-icon" />
        <h2 class="level-title">LEVEL UP!</h2>
        <p class="dweller-name">{{ dwellerName }}</p>
        <p class="level-number">LEVEL {{ newLevel }}</p>
        <div class="stats-gained">
          <div class="stat-item">
            <Icon icon="mdi:heart-plus" class="stat-icon hp-icon" />
            <span>+{{ hpGain }} HP</span>
          </div>
          <div v-if="totalXP > 0" class="stat-item">
            <Icon icon="mdi:star" class="stat-icon xp-icon" />
            <span>{{ totalXP.toLocaleString() }} XP Earned</span>
          </div>
        </div>
        <div class="scanlines"></div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.level-up-notification {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(4px);
}

.level-up-content {
  position: relative;
  padding: 3rem;
  text-align: center;
  background: linear-gradient(
    135deg,
    rgb(0 0 0 / 0.9) 0%,
    rgb(15 23 42 / 0.9) 100%
  );
  border: 2px solid rgb(250 204 21);
  border-radius: 0.5rem;
  box-shadow:
    0 0 30px rgb(250 204 21 / 0.5),
    0 0 60px rgb(250 204 21 / 0.3),
    inset 0 0 20px rgb(0 0 0 / 0.5);
  animation: reveal 0.5s ease-out;
  overflow: hidden;
}

.level-icon {
  font-size: 6rem;
  color: rgb(250 204 21);
  margin-bottom: 1rem;
  animation: bounce 1s ease-in-out infinite;
  filter: drop-shadow(0 0 12px rgb(250 204 21 / 0.8));
}

.level-title {
  font-size: 3rem;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  color: rgb(250 204 21);
  margin: 0 0 1rem 0;
  text-shadow:
    0 0 10px rgb(250 204 21 / 0.8),
    0 0 20px rgb(250 204 21 / 0.5),
    0 0 30px rgb(250 204 21 / 0.3);
  letter-spacing: 0.2em;
  animation: glow 2s ease-in-out infinite;
}

.dweller-name {
  font-size: 1.5rem;
  color: rgb(34 197 94);
  margin: 0 0 0.5rem 0;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 8px rgb(34 197 94 / 0.5);
}

.level-number {
  font-size: 2rem;
  color: rgb(251 191 36);
  margin: 0 0 2rem 0;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 8px rgb(251 191 36 / 0.6);
}

.stats-gained {
  display: flex;
  gap: 2rem;
  justify-content: center;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  color: rgb(134 239 172);
  font-family: 'Courier New', monospace;
  padding: 0.75rem 1.5rem;
  background: rgb(0 0 0 / 0.5);
  border: 1px solid rgb(34 197 94 / 0.5);
  border-radius: 0.25rem;
  box-shadow: inset 0 0 10px rgb(0 0 0 / 0.5);
}

.stat-icon {
  font-size: 1.5rem;
}

.hp-icon {
  color: rgb(239 68 68);
  filter: drop-shadow(0 0 4px rgb(239 68 68 / 0.6));
}

.xp-icon {
  color: rgb(250 204 21);
  filter: drop-shadow(0 0 4px rgb(250 204 21 / 0.6));
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 0, 0, 0.1) 0px,
    transparent 1px,
    transparent 2px,
    rgba(0, 0, 0, 0.1) 3px
  );
  opacity: 0.3;
}

/* Animations */
@keyframes reveal {
  0% {
    opacity: 0;
    transform: scale(0.5) rotateY(90deg);
  }
  100% {
    opacity: 1;
    transform: scale(1) rotateY(0deg);
  }
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

@keyframes glow {
  0%,
  100% {
    text-shadow:
      0 0 10px rgb(250 204 21 / 0.8),
      0 0 20px rgb(250 204 21 / 0.5),
      0 0 30px rgb(250 204 21 / 0.3);
  }
  50% {
    text-shadow:
      0 0 15px rgb(250 204 21 / 1),
      0 0 30px rgb(250 204 21 / 0.8),
      0 0 45px rgb(250 204 21 / 0.5);
  }
}

/* Transition animations */
.level-up-enter-active {
  animation: reveal 0.5s ease-out;
}

.level-up-leave-active {
  animation: reveal 0.3s ease-in reverse;
}
</style>
