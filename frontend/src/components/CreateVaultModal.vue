<script setup lang="ts">
import { ref } from 'vue'
import { NModal, NButton } from 'naive-ui'
import { useVaultStore } from '@/stores/vault_old'
import VaultNumberSpinner from './VaultNumberSpinner.vue'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const vaultStore = useVaultStore()
const vaultNumber = ref(Math.floor(Math.random() * 999) + 1)

const createVault = () => {
  vaultStore.createVault(vaultNumber.value)
  emit('update:modelValue', false)
}
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="(value) => emit('update:modelValue', value)"
    preset="card"
    style="width: 400px"
    title="INITIALIZING NEW VAULT"
    :bordered="false"
    class="vault-creation-modal"
  >
    <div class="creation-content">
      <div class="vault-number">
        <div class="label">VAULT NUMBER</div>
        <VaultNumberSpinner :final-number="vaultNumber" />
      </div>

      <NButton type="primary" block @click="createVault"> INITIALIZE VAULT</NButton>
    </div>
  </NModal>
</template>

<style scoped>
.vault-creation-modal {
  background: #000000;
  border: 2px solid #00ff00;
}

.creation-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 16px;
}

.vault-number {
  text-align: center;
}

.label {
  margin-bottom: 12px;
  font-family: 'Courier New', monospace;
  opacity: 0.8;
}
</style>
