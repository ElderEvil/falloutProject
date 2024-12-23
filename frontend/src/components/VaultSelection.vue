<script setup lang="ts">
import { ref } from 'vue'
import { useVaultStore } from '@/stores/vault'
import { useRouter } from 'vue-router'
import { NCard, NGrid, NGi, NButton, NSpace } from 'naive-ui'
import CreateVaultModal from './CreateVaultModal.vue'

const vaultStore = useVaultStore()
const router = useRouter()
const showCreateModal = ref(false)

const emit = defineEmits<{
  'vault-selected': []
}>()

const selectVault = (vaultId: number) => {
  vaultStore.selectVault(vaultId)
  router.push(`/vault/${vaultId}`)
  emit('vault-selected')
}
</script>

<template>
  <div class="vault-selection">
    <NSpace justify="end" class="header-actions">
      <NButton @click="showCreateModal = true"> CREATE NEW VAULT</NButton>
    </NSpace>

    <NGrid :cols="2" :x-gap="12" :y-gap="12">
      <NGi v-for="vault in vaultStore.vaults" :key="vault.id">
        <NCard :title="'VAULT ' + vault.name" class="vault-card">
          <div class="vault-info">
            <p>DWELLERS: {{ vault.dwellers.length }}/{{ vault.maxDwellers }}</p>
            <div class="resources">
              <div v-for="resource in vault.resources" :key="resource.type">
                {{ resource.type.toUpperCase() }}: {{ resource.amount }}/{{ resource.capacity }}
              </div>
            </div>
          </div>
          <template #footer>
            <NButton type="primary" block @click="selectVault(vault.id)">
              ACCESS VAULT SYSTEMS
            </NButton>
          </template>
        </NCard>
      </NGi>
    </NGrid>

    <CreateVaultModal v-model="showCreateModal" />
  </div>
</template>

<style scoped>
.vault-selection {
  padding: 20px;
}

.header-actions {
  margin-bottom: 20px;
}

.vault-card {
  height: 100%;
  border: 2px solid #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
}

.vault-info {
  margin: 12px 0;
  font-family: 'Courier New', Courier, monospace;
}

.resources {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.resources > div {
  font-family: 'Courier New', Courier, monospace;
  letter-spacing: 1px;
}
</style>
