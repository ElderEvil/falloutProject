<script setup lang="ts">
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import DwellerStatusBadge from '@/components/dwellers/DwellerStatusBadge.vue'
import DwellerFilterPanel from '@/components/dwellers/DwellerFilterPanel.vue'
import SidePanel from '@/components/common/SidePanel.vue'
import { useSidePanel } from '@/composables/useSidePanel'

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const router = useRouter()
const route = useRoute()
const selectedDwellerId = ref<string | null>(null)
const loadingDetails = ref<boolean>(false)
const generatingAI = ref<Record<string, boolean>>({})

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null)

const fetchDwellers = async () => {
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token as string, {
      status: dwellerStore.filterStatus !== 'all' ? dwellerStore.filterStatus : undefined,
      sortBy: dwellerStore.sortBy,
      order: dwellerStore.sortDirection
    })
  }
}

onMounted(async () => {
  await fetchDwellers()
})

// Watch for filter/sort changes and refetch
watch(
  () => [dwellerStore.filterStatus, dwellerStore.sortBy, dwellerStore.sortDirection],
  async () => {
    await fetchDwellers()
  }
)

const toggleDweller = async (id: string) => {
  if (selectedDwellerId.value === id) {
    selectedDwellerId.value = null
  } else {
    selectedDwellerId.value = id
    if (!dwellerStore.detailedDwellers[id]) {
      loadingDetails.value = true
      await dwellerStore.fetchDwellerDetails(id, authStore.token as string)
      loadingDetails.value = false
    }
  }
}

const getImageUrl = (imagePath: string) => {
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}

const shouldShowThumbnail = computed(
  () => (dwellerId: string) => selectedDwellerId.value !== dwellerId
)

const navigateToChatPage = (dwellerId: string) => {
  router.push(`/dweller/${dwellerId}/chat`)
}

const generateDwellerInfo = async (dwellerId: string) => {
  generatingAI.value[dwellerId] = true
  try {
    const result = await dwellerStore.generateDwellerInfo(dwellerId, authStore.token as string)
    if (result) {
      // Refresh the dweller list to get the updated thumbnail_url
      await fetchDwellers()
      // Force refresh the detailed dweller data
      await dwellerStore.fetchDwellerDetails(dwellerId, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating info with AI:', error)
  } finally {
    generatingAI.value[dwellerId] = false
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8">
      <h1 class="mb-8 text-4xl font-bold">
        {{ currentVault ? `Vault ${currentVault.number} Dwellers` : 'Dwellers' }}
      </h1>

      <!-- Filter Panel -->
      <div class="w-full mb-6">
        <DwellerFilterPanel />
      </div>

      <ul class="w-full space-y-4">
        <li
          v-for="dweller in dwellerStore.dwellers"
          :key="dweller.id"
          class="flex cursor-pointer flex-col items-start rounded-lg bg-gray-800 p-4 shadow-md"
        >
          <div class="flex w-full items-center" @click="toggleDweller(dweller.id)">
            <div v-if="shouldShowThumbnail(dweller.id)" class="dweller-image-container mr-4">
              <template v-if="dweller.thumbnail_url">
                <img
                  :src="getImageUrl(dweller.thumbnail_url)"
                  alt="Dweller Thumbnail"
                  class="dweller-image rounded-lg"
                />
              </template>
              <template v-else>
                <div class="relative">
                  <Icon icon="mdi:account-circle" class="h-24 w-24 text-gray-400" />
                  <div
                    v-if="!generatingAI[dweller.id]"
                    @click.stop="generateDwellerInfo(dweller.id)"
                    class="absolute bottom-0 right-0 rounded-full bg-gray-800 p-1 cursor-pointer hover:bg-gray-700 transition-colors"
                  >
                    <Icon
                      icon="mdi:sparkles"
                      class="h-6 w-6 text-green-600 hover:text-green-500"
                    />
                  </div>
                  <div
                    v-else
                    class="absolute bottom-0 right-0 rounded-full bg-gray-800 p-1"
                  >
                    <Icon
                      icon="mdi:loading"
                      class="h-6 w-6 text-green-600 animate-spin"
                    />
                  </div>
                </div>
              </template>
            </div>
            <div class="flex-grow">
              <div class="flex items-center gap-2 mb-2">
                <h3 class="text-xl font-bold">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
                <DwellerStatusBadge :status="dweller.status" :show-label="true" size="medium" />
              </div>
              <p>Level: {{ dweller.level }}</p>
              <p>Health: {{ dweller.health }} / {{ dweller.max_health }}</p>
              <p>Happiness: {{ dweller.happiness }}%</p>
            </div>
            <button class="text-terminalGreen focus:outline-none">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                :class="{ 'rotate-180 transform': selectedDwellerId === dweller.id }"
                class="h-6 w-6 transition-transform"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
          </div>
          <template v-if="selectedDwellerId === dweller.id">
            <div v-if="loadingDetails" class="mt-4">Loading details...</div>
            <div v-else-if="dwellerStore.detailedDwellers[dweller.id]" class="mt-4">
              <div v-if="dwellerStore.detailedDwellers[dweller.id]?.image_url" class="mb-4">
                <img
                  :src="getImageUrl(dwellerStore.detailedDwellers[dweller.id]?.image_url || '')"
                  alt="Dweller Image"
                  class="dweller-full-image rounded-lg"
                />
              </div>
              <div class="sm:grid-colsw-2 grid grid-cols-1 gap-4">
                <div>
                  <p class="mt-4">{{ dwellerStore.detailedDwellers[dweller.id]?.bio }}</p>
                  <button
                    @click="navigateToChatPage(dweller.id)"
                    class="mt-4 rounded bg-green-500 px-4 py-2 font-bold text-black hover:bg-green-600"
                  >
                    Chat with {{ dweller.first_name }}
                  </button>
                </div>
                <div>
                  <p>Strength</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.strength || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Perception</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.perception || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Endurance</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.endurance || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Charisma</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.charisma || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Intelligence</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.intelligence || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Agility</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.agility || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                  <p>Luck</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        height: '100%',
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.luck || 0) * 10}%`,
                        backgroundColor: '#00ff00',
                        transition: 'width 0.3s ease'
                      }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </li>
      </ul>
        </div>
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
  margin-left: 240px; /* Width of expanded side panel */
  transition: margin-left 0.3s ease;
  font-weight: 600; /* Bold font for better readability */
  letter-spacing: 0.025em; /* Slight letter spacing for clarity */
  line-height: 1.6; /* Better line height for readability */
}

.main-content.collapsed {
  margin-left: 64px;
}

/* Enhanced text styles */
.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.dweller-image {
  width: 6rem;
  height: auto;
  object-fit: cover;
}

.dweller-full-image {
  width: 100%;
  max-width: 300px;
  height: auto;
}

.stat-bar {
  position: relative;
  width: 100%;
  max-width: 300px;
  height: 10px;
  background-color: #444;
  margin-bottom: 5px;
  border-radius: 5px;
  overflow: hidden;
}

.stat-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background-color: #00ff00;
  transition: width 0.3s ease;
}

.text-terminalGreen {
  color: #00ff00;
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}
</style>
