<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import AISettingsPanel from '../components/AISettingsPanel.vue'

const router = useRouter()
const authStore = useAuthStore()

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
  <VaultPageShell
    rail
    class="bg-terminal-background font-mono text-theme-primary [text-shadow:none]"
  >
    <PageHeader
      title="AI Provider Settings"
      icon="mdi:robot-outline"
      subtitle="Configure the AI provider, model, and routing for dweller conversations. Changes apply live without restart."
    >
      <template #back>
        <PageNavigation
          back-label="Back to Profile"
          back-to="/profile"
          :breadcrumbs="breadcrumbs"
        />
      </template>
    </PageHeader>

    <AISettingsPanel />
  </VaultPageShell>
</template>
