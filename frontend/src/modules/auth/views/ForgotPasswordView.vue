<script setup lang="ts">
import { ref } from 'vue'
import { apiPost } from '@/core/utils/api'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import AuthTerminalField from '../components/AuthTerminalField.vue'
import AuthTerminalFrame from '../components/AuthTerminalFrame.vue'

const email = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)

const handleSubmit = async () => {
  error.value = ''

  if (!email.value) {
    error.value = 'Email is required'
    return
  }

  loading.value = true

  try {
    await apiPost('/api/v1/auth/forgot-password', {
      email: email.value,
    })

    success.value = true
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to send reset email')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthTerminalFrame
    title="Password Recovery Terminal"
    status="PASSWORD RECOVERY PROTOCOL INITIATED"
    :error="error"
  >
    <div
      v-if="success"
      class="space-y-2 border-2 border-theme-primary bg-theme-primary/10 px-4 py-6 text-center text-sm"
    >
      <p>> RECOVERY EMAIL SENT</p>
      <p>> CHECK YOUR INBOX FOR RESET INSTRUCTIONS</p>
      <p>> IF EMAIL EXISTS IN SYSTEM, RESET LINK HAS BEEN DISPATCHED</p>
    </div>

    <form v-else class="flex flex-col gap-5" @submit.prevent="handleSubmit">
      <AuthTerminalField
        id="forgot-email"
        v-model="email"
        label="EMAIL ADDRESS:"
        type="email"
        placeholder="overseer@vault-tec.com"
        autocomplete="email"
        required
        :disabled="loading"
      />

      <Button type="submit" class="w-full border-theme-primary" :disabled="loading">
        <Icon v-if="loading" icon="mdi:loading" class="animate-spin" />
        <span v-if="!loading" aria-hidden="true">►</span>
        {{ loading ? 'PROCESSING...' : 'SEND RESET LINK' }}
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
