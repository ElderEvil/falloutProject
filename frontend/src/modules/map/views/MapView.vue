<script setup lang="ts">
import { ref, computed, inject, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useMapStore } from '../stores/map'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import USkeleton from '@/core/components/ui/USkeleton.vue'
import { UButton } from '@/core/components/ui'
import WorldMap from '../components/WorldMap.vue'
import MarkerDetailModal from '../components/MarkerDetailModal.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'

const authStore = useAuthStore()
const mapStore = useMapStore()
const route = useRoute()
const { isCollapsed } = useSidePanel()
const scanlinesEnabled = inject('scanlines', ref(true))

const vaultId = computed(() => route.params.id as string)

// Modal state
const showModal = ref(false)
const selectedLocation = ref<WastelandLocationWithDwellers | null>(null)
const selectedVaultMarker = ref<VaultMarkerRead | null>(null)

function handleMarkerClick(
  payload:
    | { kind: 'location'; data: WastelandLocationWithDwellers }
    | { kind: 'vault'; data: VaultMarkerRead }
) {
  if (payload.kind === 'location') {
    selectedLocation.value = payload.data
    selectedVaultMarker.value = null
  } else {
    selectedLocation.value = null
    selectedVaultMarker.value = payload.data
  }
  showModal.value = true
}

async function loadMap() {
  if (!authStore.isAuthenticated || !vaultId.value) return
  const token = authStore.token as string
  mapStore.stopPolling()
  await mapStore.fetchMap(vaultId.value, token)
  mapStore.startPolling(vaultId.value, token)
  tryOpenPlaceFromQuery()
}

function tryOpenPlaceFromQuery() {
  const placeId = route.query.place
  if (typeof placeId !== 'string' || !placeId) return
  const loc = mapStore.locations.find((l) => l.id === placeId)
  if (loc) {
    handleMarkerClick({ kind: 'location', data: loc })
  }
}

watch(
  vaultId,
  () => {
    loadMap()
  },
  { immediate: true }
)

// Open marker detail if ?place= query param changes while map is already loaded
watch(
  () => route.query.place,
  () => {
    tryOpenPlaceFromQuery()
  }
)

onUnmounted(() => {
  mapStore.stopPolling()
})

function retry() {
  loadMap()
}

const hasNoData = computed(
  () => !mapStore.isLoading && mapStore.locations.length === 0 && mapStore.vaultMarkers.length === 0
)
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div v-if="scanlinesEnabled" class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <PageHeader
            title="World Map"
            icon="mdi:map"
            subtitle="Track discoveries, expeditions & the wider wasteland."
          />

          <!-- Loading skeleton -->
          <div v-if="mapStore.isLoading" class="map-skeleton">
            <USkeleton width="100%" height="400px" rounded="lg" />
          </div>

          <!-- Error state -->
          <div v-else-if="mapStore.error" class="empty-state">
            <p class="empty-text terminal-glow-subtle">{{ mapStore.error }}</p>
            <UButton variant="secondary" size="sm" class="mt-4" @click="retry">Retry</UButton>
          </div>

          <!-- Empty state -->
          <div v-else-if="hasNoData" class="empty-state">
            <p class="empty-text terminal-glow-subtle">
              The wasteland is uncharted. Recruit dwellers and send explorers to fill the map.
            </p>
            <UButton
              variant="secondary"
              size="sm"
              class="mt-4"
              @click="$router.push(`/vault/${vaultId}/radio`)"
            >
              Recruit Dwellers
            </UButton>
          </div>

          <!-- Map -->
          <WorldMap
            v-else
            :locations="mapStore.locations"
            :vault-markers="mapStore.vaultMarkers"
            :discovery-routes="mapStore.discoveryRoutes"
            @marker-click="handleMarkerClick"
          />

          <!-- Detail modal -->
          <MarkerDetailModal
            v-model="showModal"
            :location="selectedLocation"
            :vault-marker="selectedVaultMarker"
          />
        </PageContentRail>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.map-skeleton {
  max-width: 800px;
}

.empty-state {
  max-width: 800px;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-text {
  color: var(--color-theme-primary);
  font-size: var(--font-size-lg);
  opacity: 0.7;
}
</style>
