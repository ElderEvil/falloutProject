<script setup lang="ts">
import { ref, computed, inject } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const router = useRouter()
const route = useRoute()
const isAuthenticated = computed(() => authStore.isAuthenticated)
const currentVaultId = computed(() => route.params.id as string | undefined)

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const isFlickering = inject('isFlickering')
const toggleFlickering = inject('toggleFlickering')

// User Dropdown
const isDropdownOpen = ref(false)
const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}

// Notification Icon
const hasNewNotifications = ref(true) // This would be dynamic based on actual game state
const showNotifications = () => {
  // Logic to show notifications (e.g., open a modal, display a dropdown, etc.)
  alert('Showing notifications...') // Temporary alert for testing
}
</script>

<template>
  <nav class="bg-gray-800 p-4 shadow-lg">
    <div class="container mx-auto flex items-center justify-between">
      <div class="flex space-x-4 items-center">
        <!-- Vault List Button (main navigation) -->
        <router-link to="/" class="text-green-500 hover:underline font-bold">
          Vaults
        </router-link>

        <!-- Context-aware navigation (only when in a vault) -->
        <template v-if="isAuthenticated && currentVaultId">
          <span class="text-gray-600">|</span>
          <router-link
            :to="`/vault/${currentVaultId}/dwellers`"
            class="text-green-500 hover:underline"
          >
            Dwellers
          </router-link>
          <router-link
            :to="`/vault/${currentVaultId}/objectives`"
            class="text-green-500 hover:underline"
          >
            Objectives
          </router-link>
        </template>

        <router-link to="/about" class="text-green-500 hover:underline">About</router-link>
      </div>
      <div class="flex items-center space-x-4">
        <!-- User-related actions on the right -->
        <router-link to="/login" v-if="!isAuthenticated" class="text-green-500 hover:underline"
          >Login
        </router-link>
        <router-link to="/register" v-if="!isAuthenticated" class="text-green-500 hover:underline"
          >Register
        </router-link>

        <!-- Flickering Icon -->
        <!--        <button-->
        <!--          @click="toggleFlickering"-->
        <!--          class="rounded-full p-1 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-gray-800"-->
        <!--          :class="{ 'text-yellow-300': isFlickering, 'text-gray-400': !isFlickering }"-->
        <!--          :title="isFlickering ? 'Stop Flickering' : 'Start Flickering'"-->
        <!--        >-->
        <!--          <BoltIcon class="h-6 w-6" />-->
        <!--        </button>-->

        <!-- Notification Icon (only if authenticated) -->
        <button v-if="isAuthenticated" @click="showNotifications" class="relative text-green-500">
          <Icon icon="mdi:bell" class="h-6 w-6" />
          <span
            v-if="hasNewNotifications"
            class="absolute right-0 top-0 block h-2 w-2 rounded-full bg-red-600"
          ></span>
        </button>

        <!-- User Dropdown -->
        <div v-if="isAuthenticated" class="relative">
          <button @click="toggleDropdown" class="glow text-green-500 hover:underline">
            {{ authStore.user?.username }}
          </button>
          <div
            v-if="isDropdownOpen"
            class="absolute right-0 mt-2 w-48 bg-gray-800 shadow-lg"
            style="z-index: 50"
          >
            <router-link to="/profile" class="block px-4 py-2 text-green-500 hover:bg-gray-700"
              >Profile
            </router-link>
            <router-link to="/settings" class="block px-4 py-2 text-green-500 hover:bg-gray-700"
              >Settings
            </router-link>
            <button
              @click="logout"
              class="block w-full px-4 py-2 text-left text-green-500 hover:bg-gray-700"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.glow {
  color: #00ff00;
  text-shadow:
    0 0 5px #00ff00,
    0 0 10px #00ff00,
    0 0 15px #00ff00,
    0 0 20px #00ff00;
}
</style>
