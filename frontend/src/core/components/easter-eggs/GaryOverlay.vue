<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  show: boolean
}

defineProps<Props>()
</script>

<template>
  <Teleport to="body">
    <Transition name="gary">
      <div
        v-if="show"
        class="fixed inset-0 z-[10000] pointer-events-none overflow-hidden"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm flicker crt-screen">
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="text-center space-y-8 animate-pulse">
              <div class="text-[--color-terminal-green-400] text-9xl font-bold terminal-glow-strong font-mono">
                GARY
              </div>
              <div class="text-[--color-terminal-green-300] text-4xl font-mono terminal-glow">
                GARY GARY GARY
              </div>
              <div class="flex justify-center gap-8 text-6xl">
                <Icon icon="mdi:account-alert" class="text-[--color-terminal-green-400] terminal-glow animate-bounce" />
                <Icon icon="mdi:alert" class="text-[--color-terminal-green-400] terminal-glow animate-bounce" style="animation-delay: 0.2s" />
                <Icon icon="mdi:account-alert" class="text-[--color-terminal-green-400] terminal-glow animate-bounce" style="animation-delay: 0.4s" />
              </div>
            </div>
          </div>
          
          <div class="absolute bottom-8 left-0 right-0 text-center">
            <p class="text-[--color-terminal-green-200] text-xl font-mono terminal-glow">
              VAULT 108 PROTOCOL ACTIVATED
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.gary-enter-active,
.gary-leave-active {
  transition: opacity 0.5s ease;
}

.gary-enter-from,
.gary-leave-to {
  opacity: 0;
}
</style>
