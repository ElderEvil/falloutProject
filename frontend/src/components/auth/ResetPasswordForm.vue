<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authService } from '@/services/authService'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

onMounted(() => {
  // Extract token from URL query params
  token.value = (route.query.token as string) || ''

  if (!token.value) {
    error.value = 'Invalid or missing reset token'
  }
})

const handleSubmit = async () => {
  error.value = ''

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  if (newPassword.value.length < 8) {
    error.value = 'Password must be at least 8 characters long'
    return
  }

  loading.value = true

  try {
    const response = await authService.resetPassword(token.value, newPassword.value)
    success.value = true

    // Redirect to login after 2 seconds
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err: any) {
    error.value = err.message || 'Password reset failed. The link may be invalid or expired.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-900">
    <div class="w-full max-w-sm rounded-lg bg-gray-800 p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-green-500">Set New Password</h2>

      <div v-if="success" class="space-y-4">
        <p class="rounded bg-green-900/50 p-4 text-center text-green-400">
          ✓ Password reset successful!<br />
          Redirecting to login...
        </p>
      </div>

      <form v-else @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="newPassword" class="block text-sm font-medium text-gray-300"
            >New Password:</label
          >
          <input
            type="password"
            id="newPassword"
            v-model="newPassword"
            required
            minlength="8"
            :disabled="loading || !token"
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
            :disabled="loading || !token"
            class="mt-1 w-full rounded bg-gray-700 p-2 text-white focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          :disabled="loading || !token"
          class="w-full rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ loading ? 'Resetting...' : 'Reset Password' }}
        </button>
      </form>

      <p v-if="error" class="mt-4 text-red-500">{{ error }}</p>

      <p class="mt-6 text-center text-sm text-gray-300">
        <router-link to="/login" class="text-green-500 hover:underline"
          >Back to Login</router-link
        >
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
