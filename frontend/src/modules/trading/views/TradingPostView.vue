<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import TradingPostPanel from '../components/TradingPostPanel.vue'

const route = useRoute()

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

    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Trading Post"
          icon="mdi:store"
          subtitle="Trade soft-deleted dwellers for bottle caps with other vaults"
        />

        <Tabs
          :model-value="activeTab"
          class="gap-0"
          @update:model-value="(value) => (activeTab = String(value))"
        >
          <TabsList
            class="mb-6 h-auto w-full justify-start gap-2 rounded-none border-b-2 border-(--color-theme-glow) bg-transparent p-0 group-data-horizontal/tabs:h-auto"
          >
            <TabsTrigger
              v-for="tab in tabs"
              :key="tab.key"
              :value="tab.key"
              class="-mb-0.5 h-auto flex-none rounded-none border-0 border-b-2 border-b-transparent bg-transparent px-6 py-3 text-[0.95rem] font-semibold text-(--color-theme-glow) text-shadow-[0_0_3px_var(--color-theme-glow)] transition-all duration-200 group-data-[variant=default]/tabs-list:data-active:shadow-none! hover:bg-(--color-theme-glow) hover:text-theme-primary hover:text-shadow-[0_0_6px_var(--color-theme-glow)] data-active:border-b-theme-primary data-active:bg-(--color-theme-glow) data-active:text-theme-primary data-active:text-shadow-[0_0_8px_var(--color-theme-glow)]"
            >
              {{ tab.label }}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dwellers" class="py-2 text-base">
            <TradingPostPanel :vault-id="vaultId" />
          </TabsContent>

          <TabsContent value="weapons" class="py-2 text-base">
            <div
              class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-glow p-8 text-center"
            >
              <Icon icon="mdi:sword" class="text-5xl text-theme-primary opacity-30" />
              <p class="m-0 font-mono text-sm text-theme-primary opacity-70">Weapon trading coming soon</p>
              <p class="m-0 font-mono text-xs text-theme-primary opacity-50">
                Trade weapons with other vaults in a future update
              </p>
            </div>
          </TabsContent>

          <TabsContent value="outfits" class="py-2 text-base">
            <div
              class="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-glow p-8 text-center"
            >
              <Icon icon="mdi:tshirt-crew" class="text-5xl text-theme-primary opacity-30" />
              <p class="m-0 font-mono text-sm text-theme-primary opacity-70">Outfit trading coming soon</p>
              <p class="m-0 font-mono text-xs text-theme-primary opacity-50">
                Trade outfits with other vaults in a future update
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
