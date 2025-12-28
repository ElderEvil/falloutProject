<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import VaultHeader from './VaultHeader.vue'
import VaultSwitcherModal from './VaultSwitcherModal.vue'
import DwellersSlideOver from './DwellersSlideOver.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const vaultStore = useVaultStore()

const showVaultSwitcher = ref(false)
const showDwellers = ref(false)
const currentVaultId = computed(() => route.params.vaultId as string)

const openVaultSwitcher = () => {
  showVaultSwitcher.value = true
}

const openDwellers = () => {
  showDwellers.value = true
}

onMounted(async () => {
  // Fetch vaults if not loaded
  if (!vaultStore.vaults.length && authStore.token) {
    await vaultStore.fetchVaults(authStore.token)
  }

  // Set selected vault ID to match route
  if (currentVaultId.value) {
    vaultStore.selectedVaultId = currentVaultId.value
  }
})
</script>

<template>
  <div class="min-h-screen bg-black font-mono text-primary-500">
    <!-- Scanlines effect -->
    <div class="scanlines"></div>

    <!-- Header -->
    <VaultHeader
      :current-vault-id="currentVaultId"
      @switch-vault="openVaultSwitcher"
      @open-dwellers="openDwellers"
    />

    <!-- Main Content Area -->
    <div class="container mx-auto px-4 py-6">
      <div class="border-2 border-primary-600 bg-black/80 p-4">
        <!-- Action Bar -->
        <div class="flex items-center justify-between mb-4 pb-4 border-b-2 border-primary-800">
          <h2 class="text-xl font-bold text-primary-500 uppercase">VAULT OVERVIEW</h2>
          <UButton
            color="primary"
            variant="outline"
            size="lg"
            icon="i-lucide-users"
            class="uppercase font-bold"
            @click="openDwellers"
          >
            DWELLERS
          </UButton>
        </div>

        <!-- Vault Content -->
        <router-view />
      </div>
    </div>

    <!-- Vault Switcher Modal -->
    <VaultSwitcherModal
      v-model="showVaultSwitcher"
      :current-vault-id="currentVaultId"
    />

    <!-- Dwellers Slide Over -->
    <DwellersSlideOver v-model="showDwellers" />
  </div>
</template>

<style scoped>
.scanlines {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.1),
    rgba(0, 0, 0, 0.1) 1px,
    transparent 1px,
    transparent 2px
  );
  pointer-events: none;
  z-index: 1;
}
</style>
