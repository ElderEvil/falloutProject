<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import UTabs from '@/core/components/ui/UTabs.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import TradingPostPanel from '../components/TradingPostPanel.vue'

const route = useRoute()
const { isCollapsed } = useSidePanel()

const vaultId = computed(() => route.params.id as string)

const activeTab = ref('dwellers')
const tabs = [
  { key: 'dwellers', label: 'Dwellers' },
  { key: 'weapons', label: 'Weapons' },
  { key: 'outfits', label: 'Outfits' },
]
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <SidePanel />

      <main class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail class="flex flex-col gap-6">
          <PageHeader
            title="Trading Post"
            icon="mdi:store"
            subtitle="Trade soft-deleted dwellers for bottle caps with other vaults"
          />

          <UTabs v-model="activeTab" :tabs="tabs">
            <template #default="{ activeTab: tab }">
              <TradingPostPanel v-if="tab === 'dwellers'" :vault-id="vaultId" />

              <div
                v-else-if="tab === 'weapons'"
                class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-glow p-8 text-center"
              >
                <Icon icon="mdi:sword" class="text-5xl text-theme-primary opacity-30" />
                <p class="m-0 font-mono text-sm text-theme-primary opacity-70">Weapon trading coming soon</p>
                <p class="m-0 font-mono text-xs text-theme-primary opacity-50">
                  Trade weapons with other vaults in a future update
                </p>
              </div>

              <div
                v-else
                class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-glow p-8 text-center"
              >
                <Icon icon="mdi:tshirt-crew" class="text-5xl text-theme-primary opacity-30" />
                <p class="m-0 font-mono text-sm text-theme-primary opacity-70">Outfit trading coming soon</p>
                <p class="m-0 font-mono text-xs text-theme-primary opacity-50">
                  Trade outfits with other vaults in a future update
                </p>
              </div>
            </template>
          </UTabs>
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
