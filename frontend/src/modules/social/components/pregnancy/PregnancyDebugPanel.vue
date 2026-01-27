<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { UCard, UButton } from '@/core/components/ui'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()

const pregnancyStore = usePregnancyStore()
const dwellerStore = useDwellerStore()
const authStore = useAuthStore()

const { activePregnancies } = storeToRefs(pregnancyStore)
const { dwellers } = storeToRefs(dwellerStore)
const { isSuperuser, token } = storeToRefs(authStore)

const selectedMother = ref('')
const selectedFather = ref('')

const mothers = computed(() => {
  return dwellers.value
    .filter((d) => d.gender === 'female' && d.age_group === 'adult')
    .sort((a, b) =>
      (a.first_name + ' ' + a.last_name).localeCompare(b.first_name + ' ' + b.last_name)
    )
})

const fathers = computed(() => {
  return dwellers.value
    .filter((d) => d.gender === 'male' && d.age_group === 'adult')
    .sort((a, b) =>
      (a.first_name + ' ' + a.last_name).localeCompare(b.first_name + ' ' + b.last_name)
    )
})

const handleForceConception = async () => {
  if (!selectedMother.value || !selectedFather.value) return

  await pregnancyStore.forceConception(selectedMother.value, selectedFather.value)
  selectedMother.value = ''
  selectedFather.value = ''
}

const handleAccelerate = async (id: string) => {
  await pregnancyStore.acceleratePregnancy(id)
}

// Note: Parent component (RelationshipsView) handles fetching dwellers
</script>

<template>
  <UCard v-if="isSuperuser" class="border-amber-500/50 mb-8 border-2">
    <template #header>
      <div class="flex items-center justify-between text-amber-500">
        <h3 class="font-bold tracking-wider uppercase text-sm flex items-center gap-2">
          <span>[ DEBUG CONTROL ]</span>
        </h3>
        <span class="text-xs font-mono uppercase animate-pulse">⚠ RESTRICTED ACCESS</span>
      </div>
    </template>

    <div class="space-y-6">
      <!-- Force Conception -->
      <div class="space-y-3">
        <h4
          class="text-xs font-bold uppercase tracking-widest text-gray-500 border-b border-gray-800 pb-1"
        >
          Force Conception Protocol
        </h4>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs text-gray-400 mb-1 font-mono">Mother (Female/Adult)</label>
            <div class="relative">
              <select
                v-model="selectedMother"
                class="w-full appearance-none bg-gray-900 border-2 border-gray-700 text-terminalGreen rounded px-3 py-2 focus:border-amber-500 focus:outline-none text-sm transition-colors cursor-pointer"
              >
                <option value="" disabled>Select Subject A</option>
                <option v-for="m in mothers" :key="m.id" :value="m.id">
                  {{ m.first_name }} {{ m.last_name }} (Lvl {{ m.level }})
                </option>
              </select>
              <div
                class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500"
              >
                <svg
                  class="fill-current h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                >
                  <path
                    d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"
                  />
                </svg>
              </div>
            </div>
          </div>

          <div>
            <label class="block text-xs text-gray-400 mb-1 font-mono">Father (Male/Adult)</label>
            <div class="relative">
              <select
                v-model="selectedFather"
                class="w-full appearance-none bg-gray-900 border-2 border-gray-700 text-terminalGreen rounded px-3 py-2 focus:border-amber-500 focus:outline-none text-sm transition-colors cursor-pointer"
              >
                <option value="" disabled>Select Subject B</option>
                <option v-for="f in fathers" :key="f.id" :value="f.id">
                  {{ f.first_name }} {{ f.last_name }} (Lvl {{ f.level }})
                </option>
              </select>
              <div
                class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500"
              >
                <svg
                  class="fill-current h-4 w-4"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                >
                  <path
                    d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <UButton
          variant="secondary"
          block
          :disabled="!selectedMother || !selectedFather"
          @click="handleForceConception"
          class="!border-amber-500 !text-amber-500 hover:!bg-amber-500/10 font-mono tracking-wider"
        >
          INITIATE CONCEPTION SEQUENCE
        </UButton>
      </div>

      <!-- Accelerate Pregnancy -->
      <div v-if="activePregnancies.length > 0" class="space-y-3">
        <h4
          class="text-xs font-bold uppercase tracking-widest text-gray-500 border-b border-gray-800 pb-1"
        >
          Accelerate Gestation
        </h4>

        <div class="space-y-2">
          <div
            v-for="p in activePregnancies"
            :key="p.id"
            class="flex items-center justify-between bg-gray-900/50 p-3 rounded border border-gray-800 hover:border-amber-500/30 transition-colors"
          >
            <div class="text-sm">
              <span class="text-gray-500 font-mono text-xs uppercase block mb-1">Subject</span>
              <span class="font-bold text-terminalGreen">
                {{ dwellers.find((d) => d.id === p.mother_id)?.first_name }}
                {{ dwellers.find((d) => d.id === p.mother_id)?.last_name }}
              </span>
            </div>

            <UButton
              size="sm"
              variant="secondary"
              @click="handleAccelerate(p.id)"
              :disabled="p.is_due"
              class="!border-amber-500 !text-amber-500 hover:!bg-amber-500/10 min-w-[120px]"
            >
              {{ p.is_due ? 'READY' : 'ACCELERATE' }}
            </UButton>
          </div>
        </div>
      </div>
    </div>
  </UCard>
</template>
