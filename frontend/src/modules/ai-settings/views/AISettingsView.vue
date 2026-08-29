<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import AISettingsPanel from '../components/AISettingsPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()

const isSuperuser = computed(() => authStore.isSuperuser)

const breadcrumbs = [{ label: 'Profile', to: '/profile' }, { label: 'AI Provider Settings' }]

onMounted(() => {
  if (!isSuperuser.value) {
    router.replace('/profile')
    return
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="scanlines" aria-hidden="true"></div>
    <div class="flex min-h-screen">
      <SidePanel />
      <main
        class="flex-1 flicker transition-[margin-left] duration-300 ease font-semibold tracking-[0.025em] leading-[1.6]"
        :class="isCollapsed ? 'ml-16' : 'ml-60'"
      >
        <PageContentRail>
          <PageHeader
            title="AI Provider Settings"
            icon="mdi:robot-outline"
            subtitle="Configure the AI provider, model, and routing for dweller conversations. Changes apply live without restart."
          >
            <template #back>
              <PageNavigation back-label="Back to Profile" back-to="/profile" :breadcrumbs="breadcrumbs" />
            </template>
          </PageHeader>

          <AISettingsPanel />
        </PageContentRail>
      </main>
    </div>
  </div>
</template>
