<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'

interface Props {
  currentVaultId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'switchVault'): void
  (e: 'openDwellers'): void
}>()

const router = useRouter()
const authStore = useAuthStore()
const vaultStore = useVaultStore()

const currentVault = computed(() => vaultStore.selectedVault)

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="sticky top-0 z-50 bg-black border-b-2 border-primary-600">
    <div class="flex items-center justify-between px-4 py-2">
      <!-- Left: Vault Number & Happiness -->
      <div class="flex items-center space-x-6">
        <!-- Vault Number Badge -->
        <button
          @click="emit('switchVault')"
          class="relative flex items-center justify-center w-16 h-16 bg-primary-600 rounded-full border-4 border-primary-500 hover:bg-primary-500 transition-colors cursor-pointer"
          type="button"
        >
          <div class="text-center">
            <div class="text-xs font-bold text-black uppercase leading-tight">Vault</div>
            <div class="text-2xl font-bold text-black leading-none">{{ currentVault?.number || '?' }}</div>
          </div>
        </button>

        <!-- Happiness -->
        <div v-if="currentVault" class="flex items-center space-x-2">
          <UIcon name="i-lucide-smile" class="h-8 w-8 text-primary-500" />
          <span class="text-2xl font-bold text-primary-500">{{ currentVault.happiness }}%</span>
        </div>
      </div>

      <!-- Center: Resources -->
      <div v-if="currentVault" class="flex items-center space-x-4">
        <!-- Power -->
        <div class="flex items-center space-x-2">
          <UIcon name="i-lucide-zap" class="h-6 w-6 text-primary-500" />
          <div class="w-32 h-6 bg-black border-2 border-primary-700 rounded relative overflow-hidden">
            <div
              class="h-full bg-primary-500 transition-all"
              :style="{ width: `${Math.min((currentVault.power / currentVault.power_max) * 100, 100)}%` }"
            />
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-xs font-bold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
                {{ currentVault.power }}/{{ currentVault.power_max }}
              </span>
            </div>
          </div>
        </div>

        <!-- Food -->
        <div class="flex items-center space-x-2">
          <UIcon name="i-lucide-cake" class="h-6 w-6 text-primary-500" />
          <div class="w-32 h-6 bg-black border-2 border-primary-700 rounded relative overflow-hidden">
            <div
              class="h-full bg-primary-500 transition-all"
              :style="{ width: `${Math.min((currentVault.food / currentVault.food_max) * 100, 100)}%` }"
            />
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-xs font-bold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
                {{ currentVault.food }}/{{ currentVault.food_max }}
              </span>
            </div>
          </div>
        </div>

        <!-- Water -->
        <div class="flex items-center space-x-2">
          <UIcon name="i-lucide-flask" class="h-6 w-6 text-primary-500" />
          <div class="w-32 h-6 bg-black border-2 border-primary-700 rounded relative overflow-hidden">
            <div
              class="h-full bg-primary-500 transition-all"
              :style="{ width: `${Math.min((currentVault.water / currentVault.water_max) * 100, 100)}%` }"
            />
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-xs font-bold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
                {{ currentVault.water }}/{{ currentVault.water_max }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Caps, Dwellers & Menu -->
      <div class="flex items-center space-x-4">
        <!-- Caps -->
        <div v-if="currentVault" class="flex items-center space-x-2">
          <UIcon name="i-lucide-dollar-sign" class="h-8 w-8 text-primary-500" />
          <span class="text-2xl font-bold text-primary-500">{{ currentVault.bottle_caps?.toLocaleString() }}</span>
        </div>

        <!-- Dwellers Button -->
        <button
          @click="emit('openDwellers')"
          class="flex items-center justify-center w-12 h-12 rounded-full bg-primary-600 hover:bg-primary-500 transition-colors"
          type="button"
          title="View Dwellers"
        >
          <UIcon name="i-lucide-users" class="h-6 w-6 text-black" />
        </button>

        <!-- Logout Button -->
        <button
          @click="handleLogout"
          class="flex items-center justify-center w-12 h-12 rounded-full bg-primary-600 hover:bg-primary-500 transition-colors"
          type="button"
          title="Logout"
        >
          <UIcon name="i-lucide-log-out" class="h-6 w-6 text-black" />
        </button>
      </div>
    </div>
  </header>
</template>
