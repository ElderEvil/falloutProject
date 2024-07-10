<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')

const handleSubmit = async () => {
  const success = await authStore.login(username.value, password.value)
  if (success) {
    await router.push('/')
  } else {
    error.value = 'Invalid username or password'
  }
}
</script>

<template>
  <div class="flex items-center justify-center min-h-screen bg-gray-900">
    <div class="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-sm">
      <h2 class="text-2xl font-bold text-center text-green-500 mb-6">Login</h2>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-300">Email:</label>
          <input type="email" id="username" v-model="username" required
                 class="mt-1 p-2 w-full rounded bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-green-500">
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-300">Password:</label>
          <input type="password" id="password" v-model="password" required
                 class="mt-1 p-2 w-full rounded bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-green-500">
        </div>
        <button type="submit" class="w-full py-2 px-4 bg-green-500 hover:bg-green-400 text-white font-bold rounded">
          Login
        </button>
      </form>
      <p v-if="error" class="text-red-500 mt-4">{{ error }}</p>
      <p class="mt-4 text-gray-300">Don't have an account?
        <router-link to="/register" class="text-green-500 hover:underline">Register</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
