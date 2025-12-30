<script setup lang="ts">
import { ref } from 'vue'
import axios from '@/plugins/axios'
import { useRouter } from 'vue-router'

const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

const handleSubmit = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  if (password.value.length < 8) {
    error.value = 'Password must be at least 8 characters long'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await axios.post('/api/v1/users/open', {
      username: username.value,
      email: email.value,
      password: password.value
    })

    // Show success message instead of auto-login
    success.value = true

    // Redirect to login after 3 seconds
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Registration failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-900">
    <div class="w-full max-w-sm rounded-lg bg-gray-800 p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-green-500">Register</h2>

      <!-- Success Message -->
      <div v-if="success" class="space-y-4 text-center">
        <div class="mb-4 text-6xl">✓</div>
        <p class="rounded bg-green-900/50 p-4 text-green-400">
          Account created successfully!
        </p>
        <p class="text-sm text-gray-300">
          Please check your email <strong class="text-white">{{ email }}</strong> to verify your account.
        </p>
        <p class="text-xs text-gray-400">
          Redirecting to login...
        </p>
      </div>

      <!-- Registration Form -->
      <form v-else @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium text-gray-300">Username:</label>
          <input
            type="text"
            id="username"
            v-model="username"
            required
            :disabled="loading"
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
          />
        </div>
        <div>
          <label for="email" class="block text-sm font-medium text-gray-300">Email:</label>
          <input
            type="email"
            id="email"
            v-model="email"
            required
            :disabled="loading"
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium text-gray-300">Password:</label>
          <input
            type="password"
            id="password"
            v-model="password"
            required
            minlength="8"
            :disabled="loading"
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
          />
        </div>
        <div>
          <label for="confirmPassword" class="block text-sm font-medium text-gray-300"
            >Confirm Password:</label
          >
          <input
            type="password"
            id="confirmPassword"
            v-model="confirmPassword"
            required
            minlength="8"
            :disabled="loading"
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
          />
        </div>
        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? 'Creating Account...' : 'Register' }}
        </button>
      </form>
      <p v-if="error" class="mt-4 text-red-500">{{ error }}</p>
      <p class="mt-4 text-gray-300">
        Already have an account?
        <router-link to="/login" class="text-green-500 hover:underline">Login</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
