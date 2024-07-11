<script setup lang="ts">
import { useDwellerStore } from '@/stores/dweller'
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const selectedDwellerId = ref<string | null>(null)

onMounted(async () => {
  if (authStore.isAuthenticated) {
    await dwellerStore.fetchDwellers(authStore.token as string)
  }
})

const toggleDweller = (id: string) => {
  if (selectedDwellerId.value === id) {
    selectedDwellerId.value = null
  } else {
    selectedDwellerId.value = id
  }
}

const getImageUrl = (imagePath: string) => {
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}
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
            <div class="dweller-image-container mr-4">
              <template v-if="dweller.image_url">
                <img :src="getImageUrl(dweller.image_url)" alt="Dweller Image" class="dweller-image rounded-lg"/>
              </template>
              <template v-else>
                <DwellerIcon />
              </template>
            </div>
            <div class="flex-grow">
              <h3 class="text-xl font-bold">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
            </div>
            <button class="text-terminalGreen focus:outline-none">
              <svg xmlns="http://www.w3.org/2000/svg" :class="{'transform rotate-180': selectedDwellerId === dweller.id}" class="h-6 w-6 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
          <template v-if="selectedDwellerId === dweller.id">
            <div class="mt-4">
              <p>Strength</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.strength * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Perception</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.perception * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Endurance</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.endurance * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Charisma</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.charisma * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Intelligence</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.intelligence * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Agility</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.agility * 10}%` }" class="stat-fill"></div>
              </div>
              <p>Luck</p>
              <div class="stat-bar">
                <div :style="{ width: `${dweller.luck * 10}%` }" class="stat-fill"></div>
              </div>
              <p class="mt-4">{{ dweller.bio }}</p>
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
