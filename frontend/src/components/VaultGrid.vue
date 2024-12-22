<script setup lang="ts">
import { computed, ref } from 'vue'
import { useVaultStore } from '@/stores/vault_old'
import VaultRoom from './VaultRoom.vue'
import EmptyCell from './EmptyCell.vue'
import RoomConstructionModal from './RoomConstructionModal.vue'
import { isAdjacentToExisting } from '@/utils/gridUtils'
import type { GridPosition } from '@/types/grid'

const vaultStore = useVaultStore()
const showConstructionModal = ref(false)
const selectedPosition = ref<GridPosition | null>(null)

const grid = computed(() => vaultStore.selectedVault?.grid || [])

const handleConstruct = (position: GridPosition) => {
  selectedPosition.value = position
  showConstructionModal.value = true
}

const canDig = (position: GridPosition) => {
  if (!vaultStore.selectedVault) return false
  const cell = vaultStore.selectedVault.grid[position.y][position.x]
  return cell.status === 'empty' && isAdjacentToExisting(vaultStore.selectedVault.grid, position)
}
</script>

<template>
  <div class="vault-grid">
    <div v-for="(row, y) in grid" :key="y" class="grid-row">
      <div v-for="(cell, x) in row" :key="x" class="grid-cell">
        <VaultRoom
          v-if="cell.status === 'occupied'"
          :room="vaultStore.getRoomById(cell.roomId!)!"
        />
        <EmptyCell
          v-else
          :position="{ x, y }"
          :status="cell.status"
          :can-dig="canDig({ x, y })"
          @construct="handleConstruct({ x, y })"
        />
      </div>
    </div>

    <RoomConstructionModal
      v-if="selectedPosition"
      v-model="showConstructionModal"
      :position="selectedPosition"
    />
  </div>
</template>

<style scoped>
.vault-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid var(--theme-border);
  height: calc(100vh - 400px);
  min-height: 600px;
}

.grid-row {
  display: flex;
  gap: 8px;
  flex: 1;
}

.grid-cell {
  flex: 1;
  min-width: 0;
}
</style>
