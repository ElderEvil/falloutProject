<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authService } from '@/services/authService'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const success = ref(false)
const error = ref('')
const message = ref('')

onMounted(async () => {
  const token = (route.query.token as string) || ''

  if (!token) {
    error.value = 'Invalid or missing verification token'
    loading.value = false
    return
  }

  try {
    const response = await authService.verifyEmail(token)
    success.value = true
    message.value = response.data.msg

    // Redirect to login after 3 seconds
    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (err: any) {
    error.value = err.message || 'Email verification failed. The link may be invalid or expired.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-900">
    <div class="w-full max-w-md rounded-lg bg-gray-800 p-8 shadow-lg">
      <h2 class="mb-6 text-center text-2xl font-bold text-green-500">Email Verification</h2>

      <!-- Loading State -->
      <div v-if="loading" class="text-center">
        <div class="mb-4 text-gray-300">Verifying your email...</div>
        <div class="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-gray-700 border-t-green-500"></div>
      </div>

      <!-- Success State -->
      <div v-else-if="success" class="space-y-4 text-center">
        <div class="mb-4 text-6xl">✓</div>
        <p class="rounded bg-green-900/50 p-4 text-green-400">
          {{ message || 'Email verified successfully!' }}
        </p>
        <p class="text-sm text-gray-300">
          Redirecting to login...
        </p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="space-y-4 text-center">
        <div class="mb-4 text-6xl text-red-500">✗</div>
        <p class="rounded bg-red-900/50 p-4 text-red-400">
          {{ error }}
        </p>
        <div class="mt-6 space-y-2 text-sm text-gray-300">
          <p>
            <router-link to="/login" class="text-green-500 hover:underline">Go to Login</router-link>
          </p>
          <p>
            Need a new verification link?
            <router-link to="/register" class="text-green-500 hover:underline">Register again</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
