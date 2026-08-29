<script setup lang="ts">
/**
 * About page displaying system information and version details.
 * @component
 */
import { ref, onMounted } from 'vue'
import { UCard, USkeleton, UButton } from '@/core/components/ui'
import { Icon } from '@iconify/vue'
import { systemService } from '../services/systemService'
import type { InfoResponse } from '../types/system'
import { useFakeCrash } from '@/core/composables/useFakeCrash'
import PageNavigation from '@/core/components/common/PageNavigation.vue'

const breadcrumbs = [{ label: 'Home', to: '/' }, { label: 'About' }]

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
  } catch {
    error.value = 'Failed to load backend info'
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center p-4">
    <div class="w-full max-w-2xl">
      <PageNavigation class="mb-4" back-label="Back to Home" back-to="/" :breadcrumbs="breadcrumbs" />
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
          <h3 class="text-lg font-bold text-terminal-green">Frontend</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-terminal-green-dim">Version:</span>
            <span
              class="text-terminal-green-dim cursor-pointer select-none hover:text-terminal-green-dark transition-colors"
              @click="handleVersionClick"
            >
              {{ frontendVersion }}
            </span>

            <span class="text-terminal-green-dim">Framework:</span>
            <span class="text-terminal-green-dim">Vue 3.5</span>

            <span class="text-terminal-green-dim">Build Tool:</span>
            <span class="text-terminal-green-dim">Vite (Rolldown)</span>
          </div>
        </div>

        <!-- Backend Info -->
        <div v-if="backendInfo" class="space-y-2">
          <h3 class="text-lg font-bold text-terminal-green">Backend</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-terminal-green-dim">Version:</span>
            <span class="text-terminal-green-dim">{{ backendInfo.app_version }}</span>

            <span class="text-terminal-green-dim">API Version:</span>
            <span class="text-terminal-green-dim">{{ backendInfo.api_version }}</span>

            <span class="text-terminal-green-dim">Environment:</span>
            <span class="text-terminal-green-dim">{{ backendInfo.environment }}</span>

            <span class="text-terminal-green-dim">Python:</span>
            <span class="text-terminal-green-dim">{{ backendInfo.python_version }}</span>
          </div>
        </div>

        <!-- Project Info -->
        <div class="space-y-2">
          <h3 class="text-lg font-bold text-terminal-green">Project</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <span class="text-terminal-green-dim">Name:</span>
            <span class="text-terminal-green-dim">Fallout Shelter</span>

            <span class="text-terminal-green-dim">Repository:</span>
            <a
              href="https://github.com/ElderEvil/falloutProject"
              target="_blank"
              rel="noopener noreferrer"
              class="text-terminal-green-dim hover:text-terminal-green-dark underline"
            >
              GitHub
            </a>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
