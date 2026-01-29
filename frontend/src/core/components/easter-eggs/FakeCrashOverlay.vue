<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Icon } from '@iconify/vue'

interface Props {
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  complete: []
}>()

const stage = ref<'crash' | 'reboot' | 'complete'>('crash')
const bootText = ref<string[]>([])

const crashMessages = [
  'CRITICAL SYSTEM FAILURE',
  'VAULT-TEC TERMINAL OS v2.1.0',
  '',
  'ERROR CODE: 0x0000001B',
  'INITIATING PROTOCOL 27...',
  '',
  'MEMORY DUMP IN PROGRESS',
  '███████████████████░░░░░░░░░ 67%'
]

const rebootMessages = [
  'SYSTEM REBOOT INITIATED',
  '',
  'Loading VAULT-TEC OS...',
  'Checking system integrity... OK',
  'Loading vault management systems... OK',
  'Initializing dweller database... OK',
  'Mounting resource monitors... OK',
  'Starting game engine... OK',
  '',
  'Emergency systems restored.',
  'All systems nominal.',
  '',
  'READY.'
]

const typewriterDelay = 80

const simulateCrash = async () => {
  stage.value = 'crash'
  await new Promise((resolve) => setTimeout(resolve, 3000))
  stage.value = 'reboot'
  await typewriterEffect()
  stage.value = 'complete'
  await new Promise((resolve) => setTimeout(resolve, 1000))
  emit('complete')
}

const typewriterEffect = async () => {
  bootText.value = []
  for (const line of rebootMessages) {
    bootText.value.push(line)
    await new Promise((resolve) => setTimeout(resolve, typewriterDelay))
  }
}

watch(
  () => props.show,
  (newShow) => {
    if (newShow) {
      simulateCrash()
    } else {
      bootText.value = []
      stage.value = 'crash'
    }
  }
)

onMounted(() => {
  if (props.show) {
    simulateCrash()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="crash">
      <div
        v-if="show"
        class="fixed inset-0 z-[10000] bg-black flex items-center justify-center crt-screen flicker"
      >
        <!-- Crash Screen -->
        <div v-if="stage === 'crash'" class="text-center space-y-4 font-mono px-8">
          <Icon
            icon="mdi:alert-octagon"
            class="h-24 w-24 text-red-500 mx-auto mb-8 animate-pulse"
          />
          <div
            v-for="(msg, idx) in crashMessages"
            :key="idx"
            class="text-[--color-terminal-green-400] text-lg terminal-glow"
            :class="{ 'text-red-400': idx === 0 || idx === 3, 'text-2xl font-bold': idx === 0 }"
          >
            {{ msg }}
          </div>
        </div>

        <!-- Reboot Screen -->
        <div v-if="stage === 'reboot'" class="font-mono px-8 w-full max-w-2xl">
          <div class="space-y-1">
            <div
              v-for="(line, idx) in bootText"
              :key="idx"
              class="text-[--color-terminal-green-400] text-sm terminal-glow"
              :class="{
                'text-lg font-bold': line.includes('REBOOT'),
                'text-[--color-terminal-green-300]': line.includes('OK'),
                'text-xl': line.includes('READY')
              }"
            >
              <span v-if="line">{{ line }}</span>
              <span v-else>&nbsp;</span>
            </div>
            <div class="text-[--color-terminal-green-400] animate-pulse">█</div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.crash-enter-active {
  animation: crash-in 0.3s ease-out;
}

.crash-leave-active {
  animation: crash-out 0.5s ease-in;
}

@keyframes crash-in {
  0% {
    opacity: 0;
    filter: brightness(3);
  }
  50% {
    opacity: 0.5;
    filter: brightness(2);
  }
  100% {
    opacity: 1;
    filter: brightness(1);
  }
}

@keyframes crash-out {
  0% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}
</style>
