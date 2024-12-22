<script setup lang="ts">
import { computed } from 'vue'
import { useVaultStore } from '@/stores/vault_old'
import { NCard } from 'naive-ui'
import VueDraggable from 'vuedraggable'
import DwellerCard from '@/components/dweller/DwellerCard.vue'
import VaultGrid from './VaultGrid.vue'
import NavigationHeader from './NavigationHeader.vue'
import ResourceDisplay from './ResourceDisplay.vue'

const vaultStore = useVaultStore()

const unassignedDwellers = computed(
  () => vaultStore.selectedVault?.dwellers.filter((d) => !d.assigned) || []
)

const totalDwellers = computed(() => vaultStore.selectedVault?.dwellers.length || 0)

const averageHappiness = computed(() => {
  if (!vaultStore.selectedVault?.dwellers.length) return 0
  const total = vaultStore.selectedVault.dwellers.reduce(
    (sum, dweller) => sum + dweller.happiness,
    0
  )
  return total / vaultStore.selectedVault.dwellers.length
})
</script>

<template>
  <div class="vault-interface" v-if="vaultStore.selectedVault">
    <NavigationHeader />
    <NCard
      :title="`VAULT ${vaultStore.selectedVault.name} OVERSEER INTERFACE`"
      class="terminal-card"
    >
      <ResourceDisplay
        :resources="vaultStore.selectedVault.resources"
        :bottlecaps="vaultStore.selectedVault.bottlecaps"
        :total-dwellers="totalDwellers"
        :max-dwellers="vaultStore.selectedVault.maxDwellers"
        :average-happiness="averageHappiness"
      />

      <div class="dwellers-section">
        <h3>UNASSIGNED DWELLERS</h3>
        <VueDraggable
          v-model="unassignedDwellers"
          :group="{ name: 'dwellers', pull: true, put: true }"
          item-key="id"
          class="dwellers-list"
        >
          <template #item="{ element }">
            <DwellerCard :dweller="element" />
          </template>
        </VueDraggable>
      </div>

      <div class="rooms-section">
        <h3>VAULT ROOMS</h3>
        <VaultGrid />
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.vault-interface {
  padding: 20px;
  max-width: 1800px;
  margin: 0 auto;
}

.terminal-card {
  border: 2px solid var(--theme-border);
  box-shadow: 0 0 10px var(--theme-shadow);
}

.dwellers-section {
  margin-top: 24px;
}

.dwellers-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
  margin-top: 16px;
  min-height: 100px;
  padding: 8px;
  border: 1px dashed var(--theme-border);
}

.rooms-section {
  margin-top: 24px;
}

h3 {
  font-family: 'Courier New', Courier, monospace;
  letter-spacing: 1px;
  margin: 0;
}
</style>
