<script setup lang="ts">
/**
 * About page displaying system information and version details.
 * @component
 */
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Skeleton } from '@/core/components/ui/skeleton'
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
  <div class="flex min-h-screen flex-col items-center justify-center p-4 [text-shadow:none]">
    <div class="w-full max-w-2xl">
      <PageNavigation class="mb-4" back-label="Back to Home" back-to="/" :breadcrumbs="breadcrumbs" />
    </div>
    <Card class="w-full max-w-2xl gap-0 border-theme-primary/20 bg-surface">
      <CardHeader class="border-b border-theme-primary/20 pb-4">
        <CardTitle class="text-xl font-bold text-theme-primary">About Fallout Shelter</CardTitle>
        <CardDescription>Application and system information</CardDescription>
      </CardHeader>
      <CardContent class="pt-4">
        <div v-if="isLoading" class="space-y-4">
          <Skeleton class="h-6 w-full" />
          <Skeleton class="h-6 w-3/4" />
          <Skeleton class="h-6 w-5/6" />
          <Skeleton class="h-6 w-2/3" />
        </div>

        <div v-else-if="error" class="text-red-500 font-mono">
          {{ error }}
        </div>

        <div v-else class="space-y-6 font-mono">
          <!-- Frontend Info -->
          <div class="space-y-2">
            <h3 class="text-lg font-bold text-theme-primary">Frontend</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <span class="text-theme-primary/65">Version:</span>
              <span
                class="text-theme-primary/65 cursor-pointer select-none hover:text-theme-primary transition-colors"
                @click="handleVersionClick"
              >
                {{ frontendVersion }}
              </span>

              <span class="text-theme-primary/65">Framework:</span>
              <span class="text-theme-primary/65">Vue 3.5</span>

              <span class="text-theme-primary/65">Build Tool:</span>
              <span class="text-theme-primary/65">Vite (Rolldown)</span>
            </div>
          </div>

          <!-- Backend Info -->
          <div v-if="backendInfo" class="space-y-2">
            <h3 class="text-lg font-bold text-theme-primary">Backend</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <span class="text-theme-primary/65">Version:</span>
              <span class="text-theme-primary/65">{{ backendInfo.app_version }}</span>

              <span class="text-theme-primary/65">API Version:</span>
              <span class="text-theme-primary/65">{{ backendInfo.api_version }}</span>

              <span class="text-theme-primary/65">Environment:</span>
              <span class="text-theme-primary/65">{{ backendInfo.environment }}</span>

              <span class="text-theme-primary/65">Python:</span>
              <span class="text-theme-primary/65">{{ backendInfo.python_version }}</span>
            </div>
          </div>

          <!-- Project Info -->
          <div class="space-y-2">
            <h3 class="text-lg font-bold text-theme-primary">Project</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <span class="text-theme-primary/65">Name:</span>
              <span class="text-theme-primary/65">Fallout Shelter</span>

              <span class="text-theme-primary/65">Repository:</span>
              <a
                href="https://github.com/ElderEvil/falloutProject"
                target="_blank"
                rel="noopener noreferrer"
                class="text-theme-primary/65 hover:text-theme-primary underline"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
