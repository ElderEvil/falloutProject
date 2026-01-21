<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')

const handleSubmit = async () => {
  error.value = ''
  const success = await authStore.login(username.value, password.value)
  if (success) {
    await router.push('/')
  } else {
    error.value = 'Invalid username or password'
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-900">
    <div class="w-full max-w-sm rounded-lg bg-gray-800 p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-green-500">Login</h2>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-300">Email:</label>
          <input
            type="email"
            id="username"
            v-model="username"
            required
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-300">Password:</label>
          <input
            type="password"
            id="password"
            v-model="password"
            required
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500"
          />
        </div>
        <button
          type="submit"
          class="w-full rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-400"
        >
          Login
        </button>
      </form>
      <p v-if="error" class="mt-4 text-red-500">{{ error }}</p>
      <p class="mt-4 text-gray-300">
        Don't have an account?
        <router-link to="/register" class="text-green-500 hover:underline">Register</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
