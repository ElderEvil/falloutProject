<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiPost } from '@/core/utils/api'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import AuthTerminalField from '../components/AuthTerminalField.vue'
import AuthTerminalFrame from '../components/AuthTerminalFrame.vue'

const route = useRoute()
const router = useRouter()

const token = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) {
    error.value = 'Invalid or missing reset token'
  }
})

const handleSubmit = async () => {
  error.value = ''

  if (newPassword.value.length < 8) {
    error.value = 'Password must be at least 8 characters'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  loading.value = true

  try {
    await apiPost('/api/v1/auth/reset-password', {
      token: token.value,
      new_password: newPassword.value,
    })

    success.value = true

    setTimeout(() => {
      router.push('/login')
    }, 3000)
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to reset password')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthTerminalFrame
    title="Password Reset Terminal"
    status="SECURITY PROTOCOL INITIATED"
    :error="error"
  >
    <div
      v-if="success"
      class="space-y-2 border-2 border-theme-primary bg-theme-primary/10 px-4 py-6 text-center text-sm"
    >
      <p>> PASSWORD RESET SUCCESSFUL</p>
      <p>> REDIRECTING TO LOGIN TERMINAL...</p>
    </div>

    <form v-else class="flex flex-col gap-5" @submit.prevent="handleSubmit">
      <AuthTerminalField
        id="reset-new-password"
        v-model="newPassword"
        label="NEW PASSPHRASE:"
        type="password"
        placeholder="Minimum 8 characters"
        autocomplete="new-password"
        required
        :disabled="loading"
      />
      <AuthTerminalField
        id="reset-confirm-password"
        v-model="confirmPassword"
        label="CONFIRM PASSPHRASE:"
        type="password"
        placeholder="Re-enter passphrase"
        autocomplete="new-password"
        required
        :disabled="loading"
      />

      <Button type="submit" class="w-full border-theme-primary" :disabled="loading || !token">
        <Icon v-if="loading" icon="mdi:loading" class="animate-spin" />
        <span v-if="!loading" aria-hidden="true">►</span>
        {{ loading ? 'PROCESSING...' : 'RESET PASSWORD' }}
        <span v-if="!loading" aria-hidden="true">◄</span>
      </Button>
    </form>

    <template #links>
      <p>
        > RETURN TO LOGIN:
        <router-link
          to="/login"
          class="font-bold text-theme-primary underline underline-offset-4 hover:text-theme-primary/80"
        >
          ACCESS TERMINAL
        </router-link>
      </p>
    </template>
  </AuthTerminalFrame>
</template>
