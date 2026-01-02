<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <!-- Main View -->
    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8 lg:px-8">
          <div class="max-w-4xl mx-auto">
            <!-- Header -->
            <div class="mb-8">
              <h1 class="text-4xl font-bold text-green-400 mb-2 flex items-center gap-3">
                <Icon icon="mdi:radio-tower" class="text-5xl" />
                Radio Room
              </h1>
              <p class="text-gray-400">
                Broadcast signals to attract new dwellers from the wasteland
              </p>
            </div>

            <!-- Radio Stats and Manual Recruitment -->
            <RadioStatsPanel
              v-if="vaultId"
              :vaultId="vaultId"
              @manual-recruit="handleManualRecruit"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/composables/useSidePanel'
import { useRadioStore } from '@/stores/radio'
import { useDwellerStore } from '@/stores/dweller'
import { useVaultStore } from '@/stores/vault'
import { useAuthStore } from '@/stores/auth'
import SidePanel from '@/components/common/SidePanel.vue'
import RadioStatsPanel from '@/components/radio/RadioStatsPanel.vue'

const route = useRoute()
const { isCollapsed } = useSidePanel()
const radioStore = useRadioStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const authStore = useAuthStore()

const vaultId = computed(() => route.params.id as string)

async function handleManualRecruit() {
  if (!vaultId.value) return

  const result = await radioStore.manualRecruit(vaultId.value)
  if (result) {
    // Refresh dwellers and vault data
    if (authStore.token) {
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
      await vaultStore.refreshVault(vaultId.value, authStore.token)
    }
  }
}
</script>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.main-content.collapsed {
  margin-left: 60px;
}

.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0) 50%,
    rgba(0, 255, 0, 0.02) 50%
  );
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1000;
}

.flicker {
  animation: flicker 0.15s infinite;
}

@keyframes flicker {
  0% {
    opacity: 0.98;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.98;
  }
}
</style>
