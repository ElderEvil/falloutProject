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
          <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="mb-8">
              <div class="flex items-center justify-between mb-2">
                <h1 class="text-4xl font-bold flex items-center gap-3" :style="{ color: 'var(--color-theme-primary)' }">
                  <Icon icon="mdi:heart-multiple" class="text-5xl" />
                  Dweller Relationships
                </h1>
                <UButton
                  @click="handleQuickPair"
                  :disabled="isLoading"
                  variant="primary"
                  size="sm"
                >
                  {{ isLoading ? 'Pairing...' : '⚡ Quick Pair' }}
                </UButton>
              </div>
              <p class="text-gray-400">
                Manage relationships between dwellers in your vault
              </p>
            </div>

            <!-- Pregnancy Tracker -->
            <div class="mb-8">
              <PregnancyTracker v-if="vaultId" :vaultId="vaultId" :autoRefresh="true" />
            </div>

            <!-- Relationship List -->
            <RelationshipList v-if="vaultId" :vaultId="vaultId" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useSidePanel } from '@/composables/useSidePanel'
import { useRelationshipStore } from '@/stores/relationship'
import SidePanel from '@/components/common/SidePanel.vue'
import RelationshipList from '@/components/relationships/RelationshipList.vue'
import PregnancyTracker from '@/components/pregnancy/PregnancyTracker.vue'
import UButton from '@/components/ui/UButton.vue'

const route = useRoute()
const { isCollapsed } = useSidePanel()
const relationshipStore = useRelationshipStore()

const vaultId = computed(() => route.params.id as string)
const isLoading = ref(false)

async function handleQuickPair() {
  if (!vaultId.value) return

  isLoading.value = true
  const result = await relationshipStore.quickPair(vaultId.value)
  isLoading.value = false

  if (result) {
    // Refresh relationships list
    await relationshipStore.fetchVaultRelationships(vaultId.value)
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
