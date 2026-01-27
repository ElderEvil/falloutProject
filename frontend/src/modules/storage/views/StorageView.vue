<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { storageService, type StorageItemsResponse } from '../services/storageService'
import { Icon } from '@iconify/vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import StorageItemCard from '../components/StorageItemCard.vue'

const route = useRoute()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const isLoading = ref(false)
const storageSpace = ref<{
  used_space: number
  max_space: number
  available_space: number
  utilization_pct: number
} | null>(null)

const storageItems = ref<StorageItemsResponse>({
  weapons: [],
  outfits: [],
  junk: [],
})

const activeTab = ref<'weapons' | 'outfits' | 'junk'>('weapons')

// Fetch storage data
const fetchStorageData = async () => {
  if (!vaultId.value || !authStore.token) return

  isLoading.value = true
  try {
    const [spaceData, itemsData] = await Promise.all([
      storageService.getStorageSpace(vaultId.value),
      storageService.getStorageItems(vaultId.value),
    ])

    storageSpace.value = spaceData
    storageItems.value = itemsData
  } catch (error) {
    console.error('Failed to load storage data:', error)
    toast.error('Failed to load storage data')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  fetchStorageData()
})

// Computed item lists
const weapons = computed(() => storageItems.value.weapons || [])
const outfits = computed(() => storageItems.value.outfits || [])
const junk = computed(() => storageItems.value.junk || [])

const totalItems = computed(() => weapons.value.length + outfits.value.length + junk.value.length)

// Group junk items by name and add count
const groupedJunk = computed(() => {
  const grouped = new Map<string, { item: any; count: number; ids: string[] }>()

  junk.value.forEach(junkItem => {
    const key = `${junkItem.name}-${junkItem.rarity}`
    if (grouped.has(key)) {
      const group = grouped.get(key)!
      group.count++
      group.ids.push(junkItem.id)
    } else {
      grouped.set(key, {
        item: junkItem,
        count: 1,
        ids: [junkItem.id]
      })
    }
  })

  return Array.from(grouped.values())
})

// Active items based on tab
const activeItems = computed(() => {
  switch (activeTab.value) {
    case 'weapons':
      return weapons.value
    case 'outfits':
      return outfits.value
    case 'junk':
      return groupedJunk.value
    default:
      return []
  }
})

// Sell item handler
const handleSellItem = async (itemId: string | string[], itemType: 'weapon' | 'outfit' | 'junk' | 'weapons' | 'outfits') => {
  try {
    // Normalize type
    const normalizedType = itemType === 'weapons' ? 'weapon' : itemType === 'outfits' ? 'outfit' : itemType

    const itemIds = Array.isArray(itemId) ? itemId : [itemId]
    console.log('[StorageView] Selling items:', itemIds, 'type:', normalizedType)

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

    toast.success(itemIds.length > 1 ? `Sold ${itemIds.length} items successfully` : 'Item sold successfully')

    // Force refresh storage and vault data
    console.log('[StorageView] Refreshing storage after sell...')
    await fetchStorageData()
    if (vaultId.value && authStore.token) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
    }
    console.log('[StorageView] Refresh complete')
  } catch (error) {
    console.error('Failed to sell item:', error)
    toast.error('Failed to sell item')
  }
}

// Scrap item handler
const handleScrapItem = async (itemId: string, itemType: 'weapon' | 'outfit' | 'weapons' | 'outfits') => {
  try {
    // Normalize type
    const normalizedType = itemType === 'weapons' ? 'weapon' : itemType === 'outfits' ? 'outfit' : itemType

    console.log('[StorageView] Scrapping item:', itemId, 'type:', normalizedType)

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
    console.log('[StorageView] Refreshing storage after scrap...')
    await fetchStorageData()
    if (vaultId.value && authStore.token) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
    }
    console.log('[StorageView] Refresh complete')
  } catch (error) {
    console.error('Failed to scrap item:', error)
    toast.error('Failed to scrap item')
  }
}

// Get rarity color
const getRarityColor = (rarity?: string) => {
  const rarityMap: Record<string, string> = {
    common: 'var(--color-rarity-common)',
    uncommon: 'var(--color-rarity-uncommon)',
    rare: 'var(--color-rarity-rare)',
    legendary: 'var(--color-rarity-legendary)',
  }
  return rarityMap[rarity?.toLowerCase() || 'common'] || rarityMap.common
}
</script>

<template>
  <div class="view-container">
    <SidePanel />

    <div class="main-content" :class="{ 'collapsed-sidebar': isCollapsed }">
      <!-- Header -->
      <div class="header">
        <div class="title-section">
          <Icon icon="mdi:package-variant" class="title-icon" />
          <h1 class="title">Vault Storage</h1>
        </div>

        <!-- Storage Space Info -->
        <div v-if="storageSpace" class="storage-info">
          <div class="space-stats">
            <span class="stat-label">Used:</span>
            <span class="stat-value">{{ storageSpace.used_space }}/{{ storageSpace.max_space }}</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${storageSpace.utilization_pct}%` }"
            ></div>
          </div>
          <div class="space-text">
            {{ storageSpace.available_space }} slots available ({{ storageSpace.utilization_pct.toFixed(1) }}% full)
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: activeTab === 'weapons' }"
          @click="activeTab = 'weapons'"
        >
          <Icon icon="mdi:pistol" class="tab-icon" />
          <span>Weapons</span>
          <span class="tab-count">{{ weapons.length }}</span>
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'outfits' }"
          @click="activeTab = 'outfits'"
        >
          <Icon icon="mdi:tshirt-crew" class="tab-icon" />
          <span>Outfits</span>
          <span class="tab-count">{{ outfits.length }}</span>
        </button>
        <button
          class="tab"
          :class="{ active: activeTab === 'junk' }"
          @click="activeTab = 'junk'"
        >
          <Icon icon="mdi:wrench" class="tab-icon" />
          <span>Junk</span>
          <span class="tab-count">{{ junk.length }}</span>
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="loading">
        <Icon icon="mdi:loading" class="spin" />
        <p>Loading storage...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="totalItems === 0" class="empty-state">
        <Icon icon="mdi:package-variant-closed" class="empty-icon" />
        <h2>Storage Empty</h2>
        <p>Your vault storage is empty. Send dwellers on explorations to find items!</p>
      </div>

      <!-- Items Grid -->
      <div v-else-if="activeItems.length === 0" class="empty-state">
        <Icon icon="mdi:package-variant-closed" class="empty-icon" />
        <h2>No {{ activeTab }} Found</h2>
        <p>You don't have any {{ activeTab }} in storage.</p>
      </div>

      <div v-else class="items-grid">
        <StorageItemCard
          v-for="item in activeItems"
          :key="activeTab === 'junk' ? item.item.id : item.id"
          :item="activeTab === 'junk' ? item.item : item"
          :item-type="activeTab"
          :count="activeTab === 'junk' ? item.count : 1"
          :ids="activeTab === 'junk' ? item.ids : [item.id]"
          :get-rarity-color="getRarityColor"
          @sell="handleSellItem(activeTab === 'junk' ? item.ids[0] : item.id, activeTab)"
          @sell-all="handleSellItem(activeTab === 'junk' ? item.ids : [item.id], activeTab)"
          @scrap="handleScrapItem(item.id, activeTab as 'weapon' | 'outfit')"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-container {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  padding: 2rem;
}

.main-content.collapsed-sidebar {
  margin-left: 64px;
}

/* Header */
.header {
  margin-bottom: 2rem;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.title-icon {
  width: 3rem;
  height: 3rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 8px var(--color-theme-glow));
}

.title {
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
  font-family: 'Courier New', monospace;
  letter-spacing: 0.05em;
}

/* Storage Info */
.storage-info {
  background: rgba(0, 0, 0, 0.6);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  padding: 1rem 1.5rem;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.space-stats {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-family: 'Courier New', monospace;
}

.stat-label {
  color: var(--color-theme-accent);
  font-size: 0.875rem;
  font-weight: 600;
}

.stat-value {
  color: var(--color-theme-primary);
  font-size: 1.125rem;
  font-weight: 700;
}

.progress-bar {
  height: 1.5rem;
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: var(--color-theme-primary);
  transition: width 0.3s ease;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.space-text {
  color: var(--color-theme-accent);
  font-size: 0.875rem;
  text-align: center;
  font-family: 'Courier New', monospace;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0;
}

.tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  color: var(--color-theme-accent);
  font-size: 1rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  bottom: -2px;
}

.tab:hover {
  color: var(--color-theme-primary);
  background: var(--color-theme-glow);
}

.tab.active {
  color: var(--color-theme-primary);
  border-bottom-color: var(--color-theme-primary);
  background: var(--color-theme-glow);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.tab-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.tab-count {
  padding: 0.125rem 0.5rem;
  background: var(--color-theme-primary);
  color: #000;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 700;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.loading .spin {
  width: 3rem;
  height: 3rem;
  margin-bottom: 1rem;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  width: 6rem;
  height: 6rem;
  color: var(--color-theme-accent);
  opacity: 0.5;
  margin-bottom: 1.5rem;
}

.empty-state h2 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  margin-bottom: 0.5rem;
  font-family: 'Courier New', monospace;
}

.empty-state p {
  color: var(--color-theme-accent);
  font-size: 1rem;
  font-family: 'Courier New', monospace;
}

/* Items Grid */
.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  padding-bottom: 2rem;
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 64px;
    padding: 1rem;
  }

  .title {
    font-size: 1.75rem;
  }

  .tabs {
    overflow-x: auto;
  }

  .items-grid {
    grid-template-columns: 1fr;
  }
}
</style>
