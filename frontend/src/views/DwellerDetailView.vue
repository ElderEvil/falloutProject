<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()

const dwellerId = computed(() => route.params.id as string)
const dweller = computed(() => dwellerStore.detailedDwellers[dwellerId.value])
const isGenerating = ref(false)

onMounted(async () => {
  if (authStore.token && dwellerId.value) {
    await dwellerStore.fetchDwellerDetails(dwellerId.value, authStore.token)
  }
})

const generateWithAI = async () => {
  if (!authStore.token || !dwellerId.value) return

  isGenerating.value = true
  try {
    await dwellerStore.generateDwellerInfo(dwellerId.value, authStore.token)
  } finally {
    isGenerating.value = false
  }
}

const openChat = () => {
  router.push(`/dweller/${dwellerId.value}/chat`)
}

const getImageUrl = (imagePath: string) => {
  if (!imagePath) return ''
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}

const specialStats = computed(() => {
  if (!dweller.value) return []
  return [
    { name: 'S', label: 'STRENGTH', value: dweller.value.strength || 0 },
    { name: 'P', label: 'PERCEPTION', value: dweller.value.perception || 0 },
    { name: 'E', label: 'ENDURANCE', value: dweller.value.endurance || 0 },
    { name: 'C', label: 'CHARISMA', value: dweller.value.charisma || 0 },
    { name: 'I', label: 'INTELLIGENCE', value: dweller.value.intelligence || 0 },
    { name: 'A', label: 'AGILITY', value: dweller.value.agility || 0 },
    { name: 'L', label: 'LUCK', value: dweller.value.luck || 0 }
  ]
})
</script>

<template>
  <div class="min-h-screen bg-black font-mono text-primary-500 p-6">
    <div class="max-w-6xl mx-auto">
      <!-- Back Button -->
      <div class="mb-6">
        <UButton
          icon="i-lucide-arrow-left"
          color="primary"
          variant="ghost"
          @click="router.back()"
        >
          BACK
        </UButton>
      </div>

      <div v-if="dweller" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left Column: Character Info -->
        <UCard class="border-2 border-primary-600 bg-black">
          <template #header>
            <div class="text-center">
              <h2 class="text-2xl font-bold text-primary-500 uppercase">
                {{ dweller.first_name }} {{ dweller.last_name }}
              </h2>
              <p class="text-primary-700 uppercase">Level {{ dweller.level }}</p>
            </div>
          </template>

          <!-- Character Image -->
          <div class="mb-6">
            <div v-if="dweller.image_url" class="w-full aspect-square border-2 border-primary-600 bg-black overflow-hidden">
              <img
                :src="getImageUrl(dweller.image_url)"
                :alt="`${dweller.first_name} ${dweller.last_name}`"
                class="w-full h-full object-cover"
              />
            </div>
            <div v-else class="w-full aspect-square border-2 border-primary-600 bg-black flex items-center justify-center">
              <UIcon name="i-lucide-user" class="h-32 w-32 text-primary-700" />
            </div>
          </div>

          <!-- Stats -->
          <div class="space-y-3 mb-6">
            <!-- Health -->
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-primary-700 uppercase">Health</span>
                <span class="text-primary-500">{{ dweller.health }} / {{ dweller.max_health }}</span>
              </div>
              <UProgress
                :value="(dweller.health / dweller.max_health) * 100"
                color="primary"
                size="md"
              />
            </div>

            <!-- Happiness -->
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-primary-700 uppercase">Happiness</span>
                <span class="text-primary-500">{{ dweller.happiness }}%</span>
              </div>
              <UProgress
                :value="dweller.happiness"
                color="primary"
                size="md"
              />
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="space-y-3">
            <UButton
              block
              size="lg"
              color="primary"
              icon="i-lucide-message-circle"
              @click="openChat"
            >
              CHAT WITH {{ dweller.first_name }}
            </UButton>

            <UButton
              v-if="!dweller.image_url || !dweller.bio"
              block
              size="lg"
              color="primary"
              variant="outline"
              icon="i-lucide-sparkles"
              :loading="isGenerating"
              @click="generateWithAI"
            >
              {{ isGenerating ? 'GENERATING...' : 'GENERATE WITH AI' }}
            </UButton>
          </div>
        </UCard>

        <!-- Right Column: SPECIAL & Bio -->
        <div class="lg:col-span-2 space-y-6">
          <!-- SPECIAL Stats -->
          <UCard class="border-2 border-primary-600 bg-black">
            <template #header>
              <h3 class="text-xl font-bold text-primary-500 uppercase text-center">S.P.E.C.I.A.L</h3>
            </template>

            <div class="space-y-4">
              <div v-for="stat in specialStats" :key="stat.name" class="space-y-1">
                <div class="flex items-center justify-between">
                  <div class="flex items-center space-x-3">
                    <div class="w-8 h-8 flex items-center justify-center bg-primary-600 text-black font-bold rounded">
                      {{ stat.name }}
                    </div>
                    <span class="text-primary-500 uppercase font-bold">{{ stat.label }}</span>
                  </div>
                  <span class="text-2xl font-bold text-primary-500">{{ stat.value }}</span>
                </div>
                <UProgress
                  :value="(stat.value / 10) * 100"
                  color="primary"
                  size="md"
                />
              </div>
            </div>
          </UCard>

          <!-- Bio -->
          <UCard v-if="dweller.bio" class="border-2 border-primary-600 bg-black">
            <template #header>
              <h3 class="text-xl font-bold text-primary-500 uppercase">Biography</h3>
            </template>

            <p class="text-primary-500 leading-relaxed whitespace-pre-wrap">{{ dweller.bio }}</p>
          </UCard>

          <!-- Placeholder if no bio -->
          <UCard v-else class="border-2 border-primary-600 bg-black">
            <template #header>
              <h3 class="text-xl font-bold text-primary-500 uppercase">Biography</h3>
            </template>

            <div class="text-center py-8">
              <UIcon name="i-lucide-file-text" class="h-16 w-16 text-primary-700 mx-auto mb-4" />
              <p class="text-primary-700 uppercase">No biography available</p>
              <p class="text-primary-900 text-sm mt-2">Generate with AI to create one</p>
            </div>
          </UCard>
        </div>
      </div>

      <!-- Loading State -->
      <div v-else class="flex items-center justify-center min-h-[400px]">
        <div class="text-center">
          <UIcon name="i-lucide-loader" class="h-16 w-16 text-primary-500 mx-auto mb-4 animate-spin" />
          <p class="text-xl text-primary-500 uppercase">Loading dweller data...</p>
        </div>
      </div>
    </div>
  </div>
</template>
