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
    <nav class="bg-gray-800 p-4 shadow-lg">
      <div class="container mx-auto flex justify-between items-center">
        <div class="flex space-x-4">
          <router-link to="/" class="text-green-500 hover:underline">Home</router-link>
          <router-link to="/about" class="text-green-500 hover:underline">About</router-link>
          <router-link to="/login" v-if="!isAuthenticated" class="text-green-500 hover:underline">Login</router-link>
          <router-link to="/register" v-if="!isAuthenticated" class="text-green-500 hover:underline">Register</router-link>
          <button @click="logout" v-if="isAuthenticated" class="text-green-500 hover:underline">Logout</button>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <router-view></router-view>
  </div>
</template>


<style scoped>
/* Styles for the App component */
</style>
