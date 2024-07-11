<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { computed } from 'vue'

const authStore = useAuthStore()
const router = useRouter()

const isAuthenticated = computed(() => authStore.isAuthenticated)

const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div>
    <!-- Navigation Bar -->
    <nav class="bg-gray-800 p-4 shadow-lg fixed w-full z-10 top-0">
      <div class="container mx-auto flex justify-between items-center">
        <div class="flex space-x-4">
          <!-- Main navigation links on the left -->
          <router-link to="/" class="text-green-500 hover:underline">Home</router-link>
          <router-link to="/vault" v-if="isAuthenticated" class="text-green-500 hover:underline">Vault</router-link>
          <router-link to="/dwellers" v-if="isAuthenticated" class="text-green-500 hover:underline">Dwellers</router-link>
          <router-link to="/about" class="text-green-500 hover:underline">About</router-link>
        </div>
        <div class="flex items-center space-x-4">
          <!-- User-related actions on the right -->
          <router-link to="/login" v-if="!isAuthenticated" class="text-green-500 hover:underline">Login</router-link>
          <router-link to="/register" v-if="!isAuthenticated" class="text-green-500 hover:underline">Register</router-link>
          <span v-if="isAuthenticated" class="text-green-500">{{ authStore.user?.username }}</span>
          <button @click="logout" v-if="isAuthenticated" class="text-green-500 hover:underline glow">Logout</button>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="mt-16">
      <router-view></router-view>
    </div>
  </div>
</template>

<style scoped>
/* Styles for the App component */
.glow {
  color: #00ff00;
  text-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00, 0 0 20px #00ff00;
}
</style>
