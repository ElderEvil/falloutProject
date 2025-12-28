<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const router = useRouter()

onMounted(async () => {
  if (authStore.isAuthenticated) {
    // Fetch vaults if not loaded
    if (!vaultStore.vaults.length && authStore.token) {
      await vaultStore.fetchVaults(authStore.token)
    }

    // Auto-navigate to last vault or first available
    if (vaultStore.vaults.length > 0) {
      const lastVaultId = localStorage.getItem('selectedVaultId')
      const vaultExists = lastVaultId && vaultStore.vaults.some(v => v.id === lastVaultId)

      if (vaultExists) {
        await router.push(`/vault/${lastVaultId}`)
      } else {
        // Navigate to most recently updated vault
        const sortedVaults = [...vaultStore.vaults].sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )
        const mostRecent = sortedVaults[0]
        if (mostRecent) {
          localStorage.setItem('selectedVaultId', mostRecent.id)
          await router.push(`/vault/${mostRecent.id}`)
        }
      }
    } else {
      // No vaults, should redirect to vault creation
      // For now, just stay on home
    }
  }
})
</script>

<template>
  <div class="min-h-screen bg-black font-mono text-primary-500 flex items-center justify-center">
    <div class="text-center">
      <UIcon name="i-lucide-loader" class="h-16 w-16 text-primary-500 mx-auto mb-4 animate-spin" />
      <p class="text-2xl uppercase tracking-wider">LOADING VAULT-TEC SYSTEMS...</p>
    </div>
  </div>
</template>
