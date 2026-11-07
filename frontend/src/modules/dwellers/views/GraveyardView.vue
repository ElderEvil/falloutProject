<script setup lang="ts">
/**
 * GraveyardView - Display permanently dead dwellers
 * @component
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Card } from '@/core/components/ui/card'
import DwellerPanelLayout from '../components/DwellerPanelLayout.vue'
import { DeadDwellerCard } from '../components/death'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { death: dwellerStore } = useDwellerStore()
const vaultStore = useVaultStore()

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))
const breadcrumbs = computed(() => [
  { label: 'Vault', to: `/vault/${vaultId.value}` },
  { label: 'Dwellers', to: `/vault/${vaultId.value}/dwellers` },
  { label: 'Graveyard' },
])

onMounted(async () => {
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchGraveyardDwellers(vaultId.value, authStore.token as string)
  }
})

const viewDwellerDetails = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}
</script>

<template>
  <DwellerPanelLayout>
    <PageHeader
      title="Graveyard"
      icon="mdi:grave-stone"
      subtitle="Memorial for permanently deceased dwellers"
    >
      <template #back>
        <PageNavigation back-label="Back to Dwellers" :breadcrumbs="breadcrumbs" />
      </template>
    </PageHeader>

    <!-- Loading State -->
    <div v-if="dwellerStore.isDeadLoading" class="w-full text-center py-12">
      <Icon icon="mdi:loading" class="h-12 w-12 animate-spin text-theme-primary mx-auto" />
      <p class="mt-4 text-theme-primary/60">Loading graveyard records...</p>
    </div>

    <!-- Empty State -->
    <Card
      v-else-if="dwellerStore.graveyardDwellers.length === 0"
      class="w-full max-w-lg text-center gap-0 rounded-lg border-2 border-theme-primary/20 p-6 shadow-glow-md ring-0 crt-screen"
    >
      <div class="py-8 px-4">
        <Icon icon="mdi:emoticon-happy" class="h-16 w-16 text-theme-primary/40 mx-auto mb-4" />
        <h3 class="text-xl font-bold text-theme-primary mb-2">No Permanent Casualties</h3>
        <p class="text-theme-primary/60 text-sm">
          The graveyard is empty. All deceased dwellers are still within the revival window.
        </p>
      </div>
    </Card>

    <!-- Graveyard Grid -->
    <div v-else class="w-full graveyard-grid">
      <DeadDwellerCard
        v-for="dweller in dwellerStore.graveyardDwellers"
        :key="dweller.id"
        :dweller="dweller"
        @view-details="viewDwellerDetails"
      />
    </div>

    <!-- Summary Footer -->
    <div v-if="dwellerStore.graveyardDwellers.length > 0" class="w-full mt-8 text-center">
      <p class="text-xs text-muted-foreground font-mono">
        {{ dwellerStore.graveyardDwellers.length }} soul{{
          dwellerStore.graveyardDwellers.length !== 1 ? 's' : ''
        }}
        laid to rest
      </p>
    </div>
  </DwellerPanelLayout>
</template>

<style scoped>
.graveyard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

@media (max-width: 640px) {
  .graveyard-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }
}
</style>
