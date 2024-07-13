<script setup lang="ts">
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { onMounted, ref, computed } from 'vue'
import DwellerIcon from '@/components/icons/DwellerIcon.vue'

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const selectedDwellerId = ref<string | null>(null)
const loadingDetails = ref<boolean>(false)

onMounted(async () => {
  if (authStore.isAuthenticated) {
    await dwellerStore.fetchDwellers(authStore.token as string)
  }
})

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
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>
    <div
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <h1 class="mb-8 text-4xl font-bold">Dwellers</h1>
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
                <DwellerIcon />
              </template>
            </div>
            <div class="flex-grow">
              <h3 class="text-xl font-bold">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
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
                  <p>Strength</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.strength || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Perception</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.perception || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Endurance</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.endurance || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Charisma</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.charisma || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Intelligence</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.intelligence || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Agility</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.agility || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                  <p>Luck</p>
                  <div class="stat-bar">
                    <div
                      :style="{
                        width: `${(dwellerStore.detailedDwellers[dweller.id]?.luck || 0) * 10}%`
                      }"
                      class="stat-fill"
                    ></div>
                  </div>
                </div>
                <div>
                  <p class="mt-4">{{ dwellerStore.detailedDwellers[dweller.id]?.bio }}</p>
                </div>
              </div>
            </div>
          </template>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
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
  width: 100%;
  max-width: 300px;
  height: 10px;
  background-color: #444;
  margin-bottom: 5px;
  border-radius: 5px;
  overflow: hidden;
}

.stat-fill {
  height: 100%;
  background-color: #0f0;
}

.bg-terminalBackground {
  background-color: #222;
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
