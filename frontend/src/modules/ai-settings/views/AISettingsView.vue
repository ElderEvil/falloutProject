<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import AISettingsPanel from '../components/AISettingsPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()

const isSuperuser = computed(() => authStore.isSuperuser)

function goBack() {
  router.push('/profile')
}

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
    <div class="vault-layout">
      <SidePanel />
      <main class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <PageHeader
            title="AI Provider Settings"
            icon="mdi:robot-outline"
            subtitle="Configure the AI provider, model, and routing for dweller conversations. Changes apply live without restart."
          >
            <template #back>
              <button
                class="flex items-center gap-1 text-sm text-theme-primary/60 hover:text-theme-primary transition-colors"
                @click="goBack"
              >
                <Icon icon="mdi:arrow-left" class="h-4 w-4" />
                Back to Profile
              </button>
            </template>
          </PageHeader>

          <AISettingsPanel />
        </PageContentRail>
      </main>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}
</style>