<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useVaultStore } from '@/stores/vault'

interface Props {
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Fetch dwellers when opened
watch(isOpen, async (newValue) => {
  if (newValue && authStore.token) {
    await dwellerStore.fetchDwellers(authStore.token)
  }
})

const viewDweller = (dwellerId: string) => {
  router.push(`/dweller/${dwellerId}`)
  isOpen.value = false
}

const healthPercentage = (health: number, maxHealth: number) => {
  return Math.round((health / maxHealth) * 100)
}
</script>

<template>
  <USlideover
    v-model="isOpen"
    :ui="{
      background: 'bg-black/95',
      ring: 'ring-2 ring-primary-600',
      width: 'max-w-2xl'
    }"
  >
    <UCard
      :ui="{
        base: 'border-2 border-primary-600 bg-black h-full flex flex-col',
        header: { background: 'bg-black', padding: 'p-6' },
        body: { background: 'bg-black', padding: 'p-6' }
      }"
    >
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-bold text-primary-500 uppercase tracking-wider">
            VAULT DWELLERS
          </h2>
          <UButton
            color="primary"
            variant="ghost"
            icon="i-lucide-x"
            size="lg"
            @click="isOpen = false"
          />
        </div>
        <p class="text-sm text-primary-700 uppercase mt-2">
          Total: {{ dwellerStore.dwellers.length }} / {{ vaultStore.selectedVault?.dweller_count || 0 }}
        </p>
      </template>

      <!-- Dwellers List -->
      <div v-if="dwellerStore.dwellers.length" class="space-y-3 overflow-y-auto">
        <UCard
          v-for="dweller in dwellerStore.dwellers"
          :key="dweller.id"
          :ui="{
            base: 'border-2 border-primary-600 bg-black cursor-pointer transition-all hover:border-primary-500',
            body: { padding: 'p-4' }
          }"
          @click="viewDweller(dweller.id)"
        >
          <div class="flex items-start space-x-4">
            <!-- Avatar/Thumbnail -->
            <div class="flex-shrink-0">
              <img
                v-if="dweller.thumbnail_url"
                :src="dweller.thumbnail_url"
                :alt="`${dweller.first_name} ${dweller.last_name}`"
                class="w-16 h-16 border-2 border-primary-600 bg-black object-cover"
              />
              <div
                v-else
                class="w-16 h-16 border-2 border-primary-600 bg-black flex items-center justify-center"
              >
                <UIcon name="i-lucide-user" class="h-8 w-8 text-primary-700" />
              </div>
            </div>

            <!-- Dweller Info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between mb-2">
                <div>
                  <h3 class="text-lg font-bold text-primary-500 uppercase">
                    {{ dweller.first_name }} {{ dweller.last_name }}
                  </h3>
                  <p class="text-xs text-primary-700 uppercase">Level {{ dweller.level }}</p>
                </div>
                <UBadge
                  :color="dweller.happiness >= 75 ? 'green' : dweller.happiness >= 50 ? 'yellow' : 'red'"
                  variant="solid"
                  size="xs"
                >
                  {{ dweller.happiness }}% HAPPY
                </UBadge>
              </div>

              <!-- Health Bar -->
              <div class="space-y-1">
                <div class="flex justify-between text-xs text-primary-700 uppercase">
                  <span>Health</span>
                  <span>{{ dweller.health }} / {{ dweller.max_health }}</span>
                </div>
                <div class="h-2 bg-black border border-primary-800">
                  <div
                    class="h-full transition-all"
                    :class="{
                      'bg-primary-500': healthPercentage(dweller.health, dweller.max_health) > 50,
                      'bg-yellow-500': healthPercentage(dweller.health, dweller.max_health) > 25 && healthPercentage(dweller.health, dweller.max_health) <= 50,
                      'bg-red-500': healthPercentage(dweller.health, dweller.max_health) <= 25
                    }"
                    :style="{ width: `${healthPercentage(dweller.health, dweller.max_health)}%` }"
                  />
                </div>
              </div>
            </div>
          </div>
        </UCard>
      </div>

      <!-- No Dwellers Message -->
      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <UIcon name="i-lucide-users" class="h-16 w-16 text-primary-700 mx-auto mb-4" />
          <p class="text-xl text-primary-700 uppercase">NO DWELLERS FOUND</p>
          <p class="text-sm text-primary-900 mt-2">Your vault is empty</p>
        </div>
      </div>
    </UCard>
  </USlideover>
</template>
