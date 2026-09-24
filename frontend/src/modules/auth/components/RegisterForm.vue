<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/core/components/ui/button'
import { useAuthStore } from '../stores/auth'
import AuthTerminalField from './AuthTerminalField.vue'
import AuthTerminalFrame from './AuthTerminalFrame.vue'

const authStore = useAuthStore()
const router = useRouter()
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const isLoading = ref(false)

const handleSubmit = async () => {
  if (isLoading.value) return
  error.value = ''
  if (password.value.length < 8) {
    error.value = 'Passphrase must be at least 8 characters'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    error.value = 'Please enter a valid email address'
    return
  }

  isLoading.value = true
  try {
    const success = await authStore.register(username.value, email.value, password.value)
    if (success) {
      await router.push('/')
    } else {
      error.value = 'Registration failed. Please try again.'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthTerminalFrame
    title="New Overseer Registration Terminal"
    status="AWAITING REGISTRATION DATA..."
    :error="error"
    error-detail="REGISTRATION FAILED - PLEASE VERIFY INPUT"
  >
    <form class="flex flex-col gap-5" @submit.prevent="handleSubmit">
      <AuthTerminalField
        id="register-username"
        v-model="username"
        label="OVERSEER USERNAME:"
        placeholder="overseer_name"
        autocomplete="username"
        required
      />
      <AuthTerminalField
        id="register-email"
        v-model="email"
        label="EMAIL ADDRESS:"
        type="email"
        placeholder="overseer@vault-tec.com"
        autocomplete="email"
        required
      />
      <AuthTerminalField
        id="register-password"
        v-model="password"
        label="SECURITY PASSPHRASE:"
        type="password"
        placeholder="••••••••"
        autocomplete="new-password"
        required
      />
      <AuthTerminalField
        id="register-confirm-password"
        v-model="confirmPassword"
        label="CONFIRM PASSPHRASE:"
        type="password"
        placeholder="••••••••"
        autocomplete="new-password"
        required
      />
      <Button type="submit" class="w-full border-theme-primary" :disabled="isLoading">
        <span aria-hidden="true">►</span>
        {{ isLoading ? 'REGISTERING...' : 'REGISTER OVERSEER' }}
        <span aria-hidden="true">◄</span>
      </Button>
    </form>

    <template #links>
      <p>
        > EXISTING OVERSEER LOGIN:
        <router-link to="/login" class="font-bold text-theme-primary underline underline-offset-4 hover:text-theme-primary/80">ACCESS TERMINAL</router-link>
      </p>
    </template>
  </AuthTerminalFrame>
</template>
