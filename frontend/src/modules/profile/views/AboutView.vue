<script setup lang="ts">
/**
 * About page displaying system information and version details.
 * @component
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { UCard, USkeleton, UButton } from '@/core/components/ui'
import { Icon } from '@iconify/vue'
import { systemService } from '../services/systemService'
import type { InfoResponse } from '../types/system'
import { useFakeCrash } from '@/core/composables/useFakeCrash'

const router = useRouter()

// Frontend version from package.json
const frontendVersion = __APP_VERSION__
const backendInfo = ref<InfoResponse | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const { handleVersionClick } = useFakeCrash()

onMounted(async () => {
  try {
    const response = await systemService.getInfo()
    backendInfo.value = response.data
  } catch (err) {
    error.value = 'Failed to load backend info'
    console.error('Failed to fetch backend info:', err)
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center p-4">
    <div class="w-full max-w-2xl">
      <UButton variant="ghost" size="sm" class="mb-4" @click="router.push('/')">
        <Icon icon="mdi:arrow-left" class="h-5 w-5 mr-1" />
        Back to Home
      </UButton>
    </div>
    <UCard title="System Information" glow crt class="w-full max-w-2xl">
      <div v-if="isLoading" class="space-y-4">
        <USkeleton class="h-6 w-full" />
        <USkeleton class="h-6 w-3/4" />
        <USkeleton class="h-6 w-5/6" />
        <USkeleton class="h-6 w-2/3" />
      </div>

      <div v-else-if="error" class="text-red-500 font-mono">
        {{ error }}
      </div>

      <div v-else class="space-y-6 font-mono">
        <!-- Frontend Info -->
        <div class="space-y-2">
          <h3 class="text-lg font-bold text-[--color-terminal-green-400]">Frontend</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-[--color-terminal-green-200]">Version:</span>
            <span
              class="text-[--color-terminal-green-100] cursor-pointer select-none hover:text-[--color-terminal-green-300] transition-colors"
              @click="handleVersionClick"
            >
              {{ frontendVersion }}
            </span>

            <span class="text-[--color-terminal-green-200]">Framework:</span>
            <span class="text-[--color-terminal-green-100]">Vue 3.5</span>

            <span class="text-[--color-terminal-green-200]">Build Tool:</span>
            <span class="text-[--color-terminal-green-100]">Vite (Rolldown)</span>
          </div>
        </div>

        <!-- Backend Info -->
        <div v-if="backendInfo" class="space-y-2">
          <h3 class="text-lg font-bold text-[--color-terminal-green-400]">Backend</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-[--color-terminal-green-200]">Version:</span>
            <span class="text-[--color-terminal-green-100]">{{ backendInfo.app_version }}</span>

            <span class="text-[--color-terminal-green-200]">API Version:</span>
            <span class="text-[--color-terminal-green-100]">{{ backendInfo.api_version }}</span>

            <span class="text-[--color-terminal-green-200]">Environment:</span>
            <span class="text-[--color-terminal-green-100]">{{ backendInfo.environment }}</span>

            <span class="text-[--color-terminal-green-200]">Python:</span>
            <span class="text-[--color-terminal-green-100]">{{ backendInfo.python_version }}</span>
          </div>
        </div>

        <!-- Project Info -->
        <div class="space-y-2">
          <h3 class="text-lg font-bold text-[--color-terminal-green-400]">Project</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-[--color-terminal-green-200]">Name:</span>
            <span class="text-[--color-terminal-green-100]">Fallout Shelter</span>

            <span class="text-[--color-terminal-green-200]">Repository:</span>
            <a
              href="https://github.com/ElderEvil/falloutProject"
              target="_blank"
              rel="noopener noreferrer"
              class="text-[--color-terminal-green-100] hover:text-[--color-terminal-green-300] underline"
            >
              GitHub
            </a>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
