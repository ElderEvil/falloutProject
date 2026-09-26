<script setup lang="ts">
/**
 * About page displaying system information and version details.
 * @component
 */
import { ref, onMounted } from 'vue'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Skeleton } from '@/core/components/ui/skeleton'
import { systemService } from '../services/systemService'
import type { InfoResponse } from '../types/system'
import { useFakeCrash } from '@/core/composables/useFakeCrash'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useVaultStore } from '@/modules/vault/stores/vault'
import PageHeader from '@/core/components/common/PageHeader.vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'

const breadcrumbs = [{ label: 'Home', to: '/' }, { label: 'About' }]

// Frontend version from package.json
const frontendVersion = __APP_VERSION__
const backendInfo = ref<InfoResponse | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const { handleVersionClick } = useFakeCrash()
const { isCollapsed } = useSidePanel()
const vaultStore = useVaultStore()

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
  <div class="min-h-screen bg-terminal-background text-theme-primary [text-shadow:none]">
    <div class="flex min-h-screen">
      <SidePanel v-if="vaultStore.currentVaultId" :vault-id="vaultStore.currentVaultId" />
      <main
        class="min-w-0 flex-1 pb-8 transition-[margin-left] duration-300 ease max-md:ml-0"
        :class="vaultStore.currentVaultId ? (isCollapsed ? 'ml-16' : 'ml-60') : ''"
      >
        <div class="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
          <PageHeader
            title="About Fallout Shelter"
            icon="mdi:information-outline"
            subtitle="A vault management game about caring for dwellers, keeping resources balanced, and exploring the wasteland."
          >
            <template #back>
              <PageNavigation back-label="Back to Home" back-to="/" :breadcrumbs="breadcrumbs" />
            </template>
          </PageHeader>

          <div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
            <Card class="gap-0 border-theme-primary/20 bg-surface">
              <CardHeader class="border-b border-theme-primary/20 pb-4">
                <CardTitle class="text-xl font-bold text-theme-primary"
                  >System information</CardTitle
                >
                <CardDescription
                  >Versions and runtime details for this installation</CardDescription
                >
              </CardHeader>
              <CardContent class="space-y-6 pt-5 font-mono">
                <section aria-labelledby="frontend-heading">
                  <h2 id="frontend-heading" class="mb-3 text-base font-semibold text-theme-primary">
                    Frontend
                  </h2>
                  <dl
                    class="grid grid-cols-[minmax(7rem,1fr)_minmax(0,1.5fr)] gap-x-4 gap-y-2 text-sm"
                  >
                    <dt class="text-theme-primary/60">Version</dt>
                    <dd class="min-w-0 break-words text-theme-primary/85">
                      <button
                        type="button"
                        class="text-left hover:text-theme-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
                        @click="handleVersionClick"
                      >
                        {{ frontendVersion }}
                      </button>
                    </dd>
                    <dt class="text-theme-primary/60">Framework</dt>
                    <dd class="text-theme-primary/85">Vue 3.5</dd>
                    <dt class="text-theme-primary/60">Build tool</dt>
                    <dd class="text-theme-primary/85">Vite (Rolldown)</dd>
                  </dl>
                </section>

                <section
                  class="border-t border-theme-primary/20 pt-5"
                  aria-labelledby="backend-heading"
                >
                  <h2 id="backend-heading" class="mb-3 text-base font-semibold text-theme-primary">
                    Backend
                  </h2>
                  <div v-if="isLoading" class="space-y-3">
                    <Skeleton class="h-5 w-full" />
                    <Skeleton class="h-5 w-4/5" />
                    <Skeleton class="h-5 w-3/5" />
                  </div>
                  <p v-else-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>
                  <dl
                    v-else-if="backendInfo"
                    class="grid grid-cols-[minmax(7rem,1fr)_minmax(0,1.5fr)] gap-x-4 gap-y-2 text-sm"
                  >
                    <dt class="text-theme-primary/60">Version</dt>
                    <dd class="min-w-0 break-words text-theme-primary/85">
                      {{ backendInfo.app_version }}
                    </dd>
                    <dt class="text-theme-primary/60">API version</dt>
                    <dd class="text-theme-primary/85">{{ backendInfo.api_version }}</dd>
                    <dt class="text-theme-primary/60">Environment</dt>
                    <dd class="text-theme-primary/85">{{ backendInfo.environment }}</dd>
                    <dt class="text-theme-primary/60">Python</dt>
                    <dd class="text-theme-primary/85">{{ backendInfo.python_version }}</dd>
                  </dl>
                </section>
              </CardContent>
            </Card>

            <Card class="gap-0 border-theme-primary/20 bg-surface">
              <CardHeader class="border-b border-theme-primary/20 pb-4">
                <CardTitle class="text-xl font-bold text-theme-primary">Project</CardTitle>
                <CardDescription>Follow releases and see what is planned</CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 pt-5 text-sm">
                <p class="leading-6 text-theme-primary/70">
                  Build your vault, assign dwellers to rooms, and send teams into the wasteland. New
                  features and changes are recorded in the changelog.
                </p>
                <nav
                  aria-label="Project links"
                  class="flex flex-col gap-3 border-t border-theme-primary/20 pt-4"
                >
                  <a
                    href="https://github.com/ElderEvil/falloutProject/blob/master/CHANGELOG.md"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="w-fit text-theme-primary underline underline-offset-2 hover:text-theme-accent"
                    >Release notes</a
                  >
                  <a
                    href="https://github.com/ElderEvil/falloutProject/blob/master/docs/ROADMAP.md"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="w-fit text-theme-primary underline underline-offset-2 hover:text-theme-accent"
                    >Roadmap</a
                  >
                  <a
                    href="https://github.com/ElderEvil/falloutProject"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="w-fit text-theme-primary underline underline-offset-2 hover:text-theme-accent"
                    >GitHub</a
                  >
                </nav>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>
