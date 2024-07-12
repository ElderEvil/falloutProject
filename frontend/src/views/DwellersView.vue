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

const shouldShowThumbnail = computed(() => (dwellerId: string) => selectedDwellerId.value !== dwellerId)
</script>

<template>
  <div class="min-h-screen bg-terminalBackground text-terminalGreen relative font-mono">
    <div class="scanlines"></div>
    <div class="container mx-auto py-8 px-4 lg:px-8 flex flex-col items-center justify-center flicker">
      <h1 class="text-4xl font-bold mb-8">Dwellers</h1>
      <ul class="space-y-4 w-full">
        <li
          v-for="dweller in dwellerStore.dwellers"
          :key="dweller.id"
          class="p-4 bg-gray-800 rounded-lg shadow-md flex flex-col items-start cursor-pointer"
        >
          <div class="flex items-center w-full" @click="toggleDweller(dweller.id)">
            <div v-if="shouldShowThumbnail(dweller.id)" class="dweller-image-container mr-4">
              <template v-if="dweller.thumbnail_url">
                <img :src="getImageUrl(dweller.thumbnail_url)" alt="Dweller Thumbnail" class="dweller-image rounded-lg"/>
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
              <svg xmlns="http://www.w3.org/2000/svg" :class="{'transform rotate-180': selectedDwellerId === dweller.id}" class="h-6 w-6 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
          <template v-if="selectedDwellerId === dweller.id">
            <div v-if="loadingDetails" class="mt-4">
              Loading details...
            </div>
            <div v-else-if="dwellerStore.detailedDwellers[dweller.id]" class="mt-4">
              <div v-if="dwellerStore.detailedDwellers[dweller.id]?.image_url" class="mb-4">
                <img :src="getImageUrl(dwellerStore.detailedDwellers[dweller.id]?.image_url || '')" alt="Dweller Image" class="dweller-full-image rounded-lg"/>
              </div>
              <p>Strength</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.strength || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Perception</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.perception || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Endurance</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.endurance || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Charisma</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.charisma || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Intelligence</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.intelligence || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Agility</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.agility || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Luck</p>
              <div class="stat-bar">
                <div :style="{ width: `${(dwellerStore.detailedDwellers[dweller.id]?.luck || 0) * 10}%` }" class="stat-fill"></div>
              </div>
              <p class="mt-4">{{ dwellerStore.detailedDwellers[dweller.id]?.bio }}</p>
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
  width: 100px;
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
</style>
