<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { storageService, type StorageItemsResponse } from '../services/storageService'
import { Icon } from '@iconify/vue'
import { UButton, UTabs } from '@/core/components/ui'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import StorageItemCard from '../components/StorageItemCard.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'

const route = useRoute()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const storageSpace = ref<{
  used_space: number
  max_space: number
  available_space: number
  utilization_pct: number
  stimpack: number
  radaway: number
} | null>(null)

const storageItems = ref<StorageItemsResponse>({
  weapons: [],
  outfits: [],
  junk: [],
})

const { run: runFetchStorageData, isLoading } = useAsyncAction(
  async (currentVaultId: string) => {
    const [spaceData, itemsData] = await Promise.all([
      storageService.getStorageSpace(currentVaultId),
      storageService.getStorageItems(currentVaultId),
    ])

    storageSpace.value = spaceData
    storageItems.value = itemsData
    return true
  },
  { context: 'Failed to load storage data', showToast: false }
)

const activeTab = ref<'weapons' | 'outfits' | 'junk'>('weapons')
type StorageTab = typeof activeTab.value
type StorageItem = StorageItemsResponse[StorageTab][number]
interface DisplayStorageItem {
  id: string
  item: StorageItem
  count: number
  ids: string[]
}

const selectTab = (tab: string) => {
  if (tab === 'weapons' || tab === 'outfits' || tab === 'junk') activeTab.value = tab
}

const tabs = computed<Array<{ key: StorageTab; label: string }>>(() => [
  { key: 'weapons', label: `Weapons (${weapons.value.length})` },
  { key: 'outfits', label: `Outfits (${outfits.value.length})` },
  { key: 'junk', label: `Junk (${junk.value.length})` },
])

// Fetch storage data
const fetchStorageData = async () => {
  if (!vaultId.value || !authStore.token) return

  const result = await runFetchStorageData(vaultId.value)
  if (!result) {
    toast.error('Failed to load storage data')
  }
}

onMounted(async () => {
  // Load vault if not already loaded
  if (vaultId.value && authStore.token && !vaultStore.loadedVaults[vaultId.value]) {
    await vaultStore.loadVault(vaultId.value, authStore.token)
  }
  fetchStorageData()
})

// Computed item lists
const weapons = computed(() => storageItems.value.weapons || [])
const outfits = computed(() => storageItems.value.outfits || [])
const junk = computed(() => storageItems.value.junk || [])

const totalItems = computed(() => weapons.value.length + outfits.value.length + junk.value.length)

// Group junk items by name and add count
const groupedJunk = computed(() => {
  const grouped = new Map<string, DisplayStorageItem>()

  junk.value.forEach((junkItem) => {
    const key = `${junkItem.name}-${junkItem.rarity}`
    if (grouped.has(key)) {
      const group = grouped.get(key)!
      group.count++
      group.ids.push(junkItem.id)
    } else {
      grouped.set(key, {
        id: junkItem.id,
        item: junkItem,
        count: 1,
        ids: [junkItem.id],
      })
    }
  })

  return Array.from(grouped.values())
})

// Active items based on tab
const activeItems = computed<DisplayStorageItem[]>(() => {
  switch (activeTab.value) {
    case 'weapons':
      return weapons.value.map((item) => ({ id: item.id, item, count: 1, ids: [item.id] }))
    case 'outfits':
      return outfits.value.map((item) => ({ id: item.id, item, count: 1, ids: [item.id] }))
    case 'junk':
      return groupedJunk.value
    default:
      return []
  }
})

// Sell item handler
const handleSellItem = async (
  itemId: string | string[],
  itemType: 'weapon' | 'outfit' | 'junk' | 'weapons' | 'outfits'
) => {
  try {
    // Normalize type
    const normalizedType =
      itemType === 'weapons' ? 'weapon' : itemType === 'outfits' ? 'outfit' : itemType

    const itemIds = Array.isArray(itemId) ? itemId : [itemId]
    // Sell all items
    for (const id of itemIds) {
      switch (normalizedType) {
        case 'weapon':
          await storageService.sellWeapon(id)
          break
        case 'outfit':
          await storageService.sellOutfit(id)
          break
        case 'junk':
          await storageService.sellJunk(id)
          break
      }
    }

    toast.success(
      itemIds.length > 1 ? `Sold ${itemIds.length} items successfully` : 'Item sold successfully'
    )

    // Force refresh storage and vault data
    await fetchStorageData()
    if (vaultId.value && authStore.token) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
    }
  } catch {
    toast.error('Failed to sell item')
  }
}

// Scrap item handler
const handleScrapItem = async (
  itemId: string,
  itemType: 'weapon' | 'outfit' | 'weapons' | 'outfits'
) => {
  try {
    // Normalize type
    const normalizedType =
      itemType === 'weapons' ? 'weapon' : itemType === 'outfits' ? 'outfit' : itemType

    switch (normalizedType) {
      case 'weapon':
        await storageService.scrapWeapon(itemId)
        break
      case 'outfit':
        await storageService.scrapOutfit(itemId)
        break
    }

    toast.success('Item scrapped for materials')

    // Force refresh storage and vault data
    await fetchStorageData()
    if (vaultId.value && authStore.token) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
    }
  } catch {
    toast.error('Failed to scrap item')
  }
}

// Get rarity color
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-theme-primary">
    <SidePanel />

    <div
      class="flex-1 transition-[margin] duration-300"
      :class="isCollapsed ? 'ml-16' : 'ml-60'"
    >
      <PageContentRail>
        <PageHeader
          title="Vault Storage"
          icon="mdi:package-variant"
          subtitle="Organize equipment, supplies & recovered wasteland loot."
        />

      <!-- Storage & Medical Supplies -->
      <div v-if="storageSpace" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div
          class="md:col-span-2 p-6 border-2 border-theme-primary/50 rounded-lg shadow-[0_0_10px_var(--color-theme-glow)] crt-screen"
        >
          <div class="flex items-center gap-3 mb-2 font-mono">
            <Icon icon="mdi:package-variant" class="w-5 h-5 text-theme-primary" />
            <span class="text-theme-accent text-xs font-semibold uppercase tracking-wider">
              {{ storageSpace.used_space }}/{{ storageSpace.max_space }} slots used
            </span>
            <span class="ml-auto text-theme-accent text-xs">
              {{ storageSpace.utilization_pct.toFixed(0) }}%
            </span>
          </div>
          <div class="h-4 bg-black/80 border border-theme-primary/50 rounded-sm overflow-hidden">
            <div
              class="h-full bg-theme-primary transition-[width] duration-300 shadow-[0_0_8px_var(--color-theme-glow)]"
              :style="{
                '--progress': `${storageSpace.utilization_pct}%`,
                width: 'var(--progress)',
              }"
            ></div>
          </div>
          <div class="text-theme-accent/60 text-xs text-right font-mono mt-1">
            {{ storageSpace.available_space }} free
          </div>
        </div>

        <div
          class="p-6 border-2 border-theme-primary/50 rounded-lg shadow-[0_0_10px_var(--color-theme-glow)] crt-screen"
        >
          <div class="flex items-center gap-4 h-full">
            <div class="flex items-center gap-2 flex-1">
              <Icon icon="mdi:medical-bag" class="w-5 h-5 text-green-500 shrink-0" />
              <div>
                <div class="text-theme-primary font-bold text-lg leading-tight">
                  {{ storageSpace.stimpack }}
                </div>
                <div class="text-theme-accent/60 text-sm">Stimpaks</div>
              </div>
            </div>
            <div class="w-px h-8 bg-theme-primary/20"></div>
            <div class="flex items-center gap-2 flex-1">
              <Icon icon="mdi:pill" class="w-5 h-5 text-(--color-caps) shrink-0" />
              <div>
                <div class="text-theme-primary font-bold text-lg leading-tight">
                  {{ storageSpace.radaway }}
                </div>
                <div class="text-theme-accent/60 text-sm">Radaways</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tabs -->
        <UTabs :model-value="activeTab" :tabs="tabs" class="mb-8" @update:model-value="selectTab">
        <!-- Loading State -->
        <div
          v-if="isLoading"
          class="flex flex-col items-center justify-center py-16 text-theme-primary font-mono"
        >
          <Icon icon="mdi:loading" class="w-12 h-12 mb-4 animate-spin" />
          <p>Loading storage...</p>
        </div>

        <!-- Empty State -->
        <TerminalEmptyState
          v-else-if="totalItems === 0"
          icon="mdi:package-variant-closed"
          title="Storage Empty"
          description="Your vault storage is empty. Send dwellers on explorations to find items!"
        />

        <!-- No Items in Category State -->
        <TerminalEmptyState
          v-else-if="activeItems.length === 0"
          icon="mdi:package-variant-closed"
          :title="`No ${activeTab} Found`"
          :description="`You don't have any ${activeTab} in storage.`"
        />

        <div v-else class="grid grid-cols-1 gap-4 pb-8 md:grid-cols-2">
          <StorageItemCard
            v-for="item in activeItems"
            :key="item.id"
            :item="item.item"
            :item-type="activeTab === 'weapons' ? 'weapon' : activeTab === 'outfits' ? 'outfit' : 'junk'"
            :count="item.count"
            @sell="handleSellItem(item.ids[0], activeTab)"
            @sell-all="handleSellItem(item.ids, activeTab)"
            @scrap="handleScrapItem(item.id, activeTab as 'weapon' | 'outfit')"
          />
        </div>
        </UTabs>
      </PageContentRail>
    </div>
  </div>
</template>
