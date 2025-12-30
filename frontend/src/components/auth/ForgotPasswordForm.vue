<script setup lang="ts">
import { ref } from 'vue'
import { authService } from '@/services/authService'
import { useRouter } from 'vue-router'

const router = useRouter()

const email = ref('')
const error = ref('')
const success = ref('')
const loading = ref(false)

const handleSubmit = async () => {
  error.value = ''
  success.value = ''
  loading.value = true

  try {
    const response = await authService.forgotPassword(email.value)
    success.value = response.data.msg
    // Clear email field
    email.value = ''
  } catch (err: any) {
    error.value = err.message || 'Failed to send password reset email. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-900">
    <div class="w-full max-w-sm rounded-lg bg-gray-800 p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-green-500">Reset Password</h2>
      <p class="mb-4 text-sm text-gray-300">
        Enter your email address and we'll send you a link to reset your password.
      </p>

      <form @submit.prevent="handleSubmit" class="space-y-4">
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

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? 'Sending...' : 'Send Reset Link' }}
        </button>
      </form>

      <p v-if="success" class="mt-4 rounded bg-green-900/50 p-3 text-sm text-green-400">
        {{ success }}
      </p>
      <p v-if="error" class="mt-4 text-red-500">{{ error }}</p>

      <div class="mt-6 space-y-2 text-center text-sm text-gray-300">
        <p>
          Remember your password?
          <router-link to="/login" class="text-green-500 hover:underline">Login</router-link>
        </p>
        <p>
          Don't have an account?
          <router-link to="/register" class="text-green-500 hover:underline">Register</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
