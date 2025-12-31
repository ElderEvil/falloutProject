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
import UTooltip from '@/components/ui/UTooltip.vue'
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
            <div class="dweller-image-container mr-4">
              <template v-if="shouldShowThumbnail(dweller.id)">
                <template v-if="dweller.thumbnail_url">
                  <img
                    :src="getImageUrl(dweller.thumbnail_url)"
                    alt="Dweller Thumbnail"
                    class="dweller-image rounded-lg"
                  />
                </template>
                <template v-else>
                  <div class="relative inline-block">
                    <Icon icon="mdi:account-circle" class="h-24 w-24 text-gray-400" />

                    <!-- Generate AI button - always visible when no thumbnail -->
                    <UTooltip
                      text="Generate AI portrait & biography"
                      position="top"
                    >
                      <div
                        @click.stop="generateDwellerInfo(dweller.id)"
                        class="ai-generate-button absolute bottom-1 right-1 rounded-full bg-gray-800 p-1 cursor-pointer hover:bg-gray-700 transition-all"
                        :class="{ 'pointer-events-none': generatingAI[dweller.id] }"
                      >
                        <Icon
                          icon="mdi:sparkles"
                          class="h-5 w-5 text-green-600"
                          :class="{ 'opacity-30': generatingAI[dweller.id] }"
                        />

                        <!-- Loading spinner overlay when generating -->
                        <div
                          v-if="generatingAI[dweller.id]"
                          class="absolute inset-0 flex items-center justify-center"
                        >
                          <Icon
                            icon="mdi:loading"
                            class="h-5 w-5 text-green-600 animate-spin"
                          />
                        </div>
                      </div>
                    </UTooltip>
                  </div>
                </template>
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
            <button
              class="expand-collapse-btn text-terminalGreen focus:outline-none p-2 rounded-full hover:bg-gray-700 transition-all"
              :aria-label="selectedDwellerId === dweller.id ? 'Collapse details' : 'Expand details'"
              :aria-expanded="selectedDwellerId === dweller.id"
            >
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
            <div v-else-if="dwellerStore.detailedDwellers[dweller.id]" class="mt-4 w-full">
              <!-- Two-Column Layout -->
              <div class="dweller-detail-layout">
                <!-- Left Column: Identity & Image -->
                <div class="identity-column">
                  <!-- Portrait Image or Placeholder -->
                  <div class="mb-4 portrait-container relative">
                    <template v-if="dwellerStore.detailedDwellers[dweller.id]?.image_url">
                      <img
                        :src="getImageUrl(dwellerStore.detailedDwellers[dweller.id]?.image_url || '')"
                        alt="Dweller Image"
                        class="dweller-full-image rounded-lg"
                      />
                    </template>
                    <template v-else>
                      <div class="dweller-full-image-placeholder rounded-lg flex items-center justify-center">
                        <Icon icon="mdi:account-circle" class="h-48 w-48 text-gray-400" />
                      </div>
                    </template>

                    <!-- Generate AI Button (Expanded View) -->
                    <UTooltip
                      v-if="!dwellerStore.detailedDwellers[dweller.id]?.image_url && !generatingAI[dweller.id]"
                      text="Generate AI portrait & biography"
                      position="top"
                    >
                      <div
                        @click.stop="generateDwellerInfo(dweller.id)"
                        class="ai-generate-button-large absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-full bg-gray-800 p-3 cursor-pointer hover:bg-gray-700 transition-all"
                      >
                        <Icon
                          icon="mdi:sparkles"
                          class="h-12 w-12 text-green-600 hover:text-green-500"
                        />
                      </div>
                    </UTooltip>

                    <!-- Loading Overlay when Generating -->
                    <div
                      v-if="generatingAI[dweller.id]"
                      class="absolute inset-0 bg-black bg-opacity-70 rounded-lg flex flex-col items-center justify-center"
                    >
                      <Icon
                        icon="mdi:loading"
                        class="h-16 w-16 text-green-600 animate-spin mb-4"
                      />
                      <p class="text-terminalGreen text-sm">Generating portrait...</p>
                    </div>
                  </div>

                  <button
                    @click="navigateToChatPage(dweller.id)"
                    class="chat-button rounded bg-green-500 px-4 py-2 font-bold text-black hover:bg-green-600 hover:shadow-[0_0_15px_rgba(0,255,0,0.6)] transition-all"
                  >
                    Chat with {{ dweller.first_name }}
                  </button>
                </div>

                <!-- Right Column: Bio & SPECIAL Stats -->
                <div class="content-column">
                  <!-- Biography Section -->
                  <div class="bio-section mb-6">
                    <h4 class="text-lg font-bold mb-2 text-terminalGreen">Biography</h4>
                    <p class="bio-text">{{ dwellerStore.detailedDwellers[dweller.id]?.bio }}</p>
                  </div>

                  <!-- SPECIAL Stats Section -->
                  <div class="stats-section">
                    <h4 class="text-lg font-bold mb-3 text-terminalGreen">S.P.E.C.I.A.L.</h4>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Strength</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.S || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.S || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Perception</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.P || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.P || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Endurance</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.E || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.E || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Charisma</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.C || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.C || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Intelligence</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.I || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.I || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Agility</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.A || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.A || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
                    <div class="stat-item">
                      <div class="stat-label-row">
                        <span class="stat-label">Luck</span>
                        <span class="stat-value">{{ dwellerStore.detailedDwellers[dweller.id]?.L || 0 }}</span>
                      </div>
                      <div class="stat-bar">
                        <div
                          class="stat-fill"
                          :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.L || 0) * 10}%` }"
                        ></div>
                      </div>
                    </div>
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

/* AI Generate Button Animation (Small - Collapsed View) */
.ai-generate-button {
  animation: pulse-glow 2s ease-in-out infinite;
  z-index: 10;
}

.ai-generate-button:hover {
  animation: none;
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.8);
}

/* AI Generate Button (Large - Expanded View) */
.ai-generate-button-large {
  animation: pulse-glow-large 2s ease-in-out infinite;
  z-index: 10;
}

.ai-generate-button-large:hover {
  animation: none;
  box-shadow: 0 0 30px rgba(0, 255, 0, 0.9);
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 5px rgba(0, 255, 0, 0.3);
  }
  50% {
    box-shadow: 0 0 15px rgba(0, 255, 0, 0.6);
  }
}

@keyframes pulse-glow-large {
  0%, 100% {
    box-shadow: 0 0 10px rgba(0, 255, 0, 0.4);
  }
  50% {
    box-shadow: 0 0 25px rgba(0, 255, 0, 0.7);
  }
}

/* Expand/Collapse Button */
.expand-collapse-btn {
  min-width: 40px;
  min-height: 40px;
}

.expand-collapse-btn:hover {
  box-shadow: 0 0 15px rgba(0, 255, 0, 0.5);
  background-color: rgba(0, 255, 0, 0.1);
}

.expand-collapse-btn:focus {
  box-shadow: 0 0 0 3px rgba(0, 255, 0, 0.4);
}

/* Two-Column Layout */
.dweller-detail-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 2rem;
  width: 100%;
}

@media (max-width: 768px) {
  .dweller-detail-layout {
    grid-template-columns: 1fr;
  }
}

/* Identity Column (Left) */
.identity-column {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.portrait-container {
  width: 100%;
  max-width: 300px;
  min-height: 300px;
}

.dweller-full-image {
  width: 100%;
  max-width: 300px;
  height: auto;
  border: 2px solid #00ff00;
  box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
}

.dweller-full-image-placeholder {
  width: 100%;
  max-width: 300px;
  min-height: 300px;
  background: rgba(0, 0, 0, 0.5);
  border: 2px dashed rgba(0, 255, 0, 0.3);
}

.chat-button {
  width: 100%;
  max-width: 300px;
}

/* Content Column (Right) */
.content-column {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Biography Section */
.bio-section {
  padding: 1rem;
  background: rgba(0, 255, 0, 0.05);
  border-left: 3px solid #00ff00;
  border-radius: 4px;
}

.bio-text {
  max-width: 65ch;
  line-height: 1.6;
  color: #00ff00;
  font-size: 0.95rem;
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.4);
}

/* SPECIAL Stats Section */
.stats-section {
  padding: 1rem;
  background: rgba(0, 255, 0, 0.05);
  border-left: 3px solid #00ff00;
  border-radius: 4px;
}

.stat-item {
  margin-bottom: 1rem;
}

.stat-item:last-child {
  margin-bottom: 0;
}

.stat-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: #00ff00;
  text-shadow: 0 0 4px rgba(0, 255, 0, 0.5);
}

.stat-value {
  font-weight: 700;
  font-size: 1rem;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.6);
  min-width: 1.5rem;
  text-align: right;
}

.stat-bar {
  position: relative;
  width: 100%;
  max-width: 500px;
  height: 12px;
  background-color: rgba(68, 68, 68, 0.8);
  border: 1px solid rgba(0, 255, 0, 0.3);
  border-radius: 6px;
  overflow: hidden;
}

.stat-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #00ff00 0%, #00cc00 100%);
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
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
