<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/core/components/ui/button'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useAuthStore } from '../stores/auth'
import AuthTerminalField from './AuthTerminalField.vue'
import AuthTerminalFrame from './AuthTerminalFrame.vue'

const authStore = useAuthStore()
const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const { run: runLogin, isLoading } = useAsyncAction(
  (currentEmail: string, currentPassword: string) => authStore.login(currentEmail, currentPassword),
  { context: 'Unable to authenticate', showToast: false }
)

const handleSubmit = async () => {
  if (isLoading.value) return
  error.value = ''
  const success = await runLogin(email.value, password.value)
  if (success) {
    await router.push('/')
  } else {
    error.value = 'Invalid username or password'
  }
}
</script>

<template>
  <AuthTerminalFrame
    title="Vault Network Access Terminal"
    status="AWAITING CREDENTIALS..."
    :error="error"
    error-detail="ACCESS DENIED - INVALID CREDENTIALS"
  >
    <form class="flex flex-col gap-5" @submit.prevent="handleSubmit">
      <AuthTerminalField
        id="login-username"
        v-model="email"
        label="USER IDENTIFICATION:"
        type="email"
        placeholder="overseer@vault-tec.com"
        autocomplete="email"
        required
      />
      <AuthTerminalField
        id="login-password"
        v-model="password"
        label="SECURITY PASSPHRASE:"
        type="password"
        placeholder="••••••••"
        autocomplete="current-password"
        required
      />
      <Button type="submit" class="w-full border-theme-primary" :disabled="isLoading">
        <span v-if="!isLoading" aria-hidden="true">►</span>
        {{ isLoading ? 'AUTHENTICATING...' : 'AUTHENTICATE' }}
        <span v-if="!isLoading" aria-hidden="true">◄</span>
      </Button>
    </form>

    <template #links>
      <p>
        > NEW OVERSEER REGISTRATION:
        <router-link to="/register" class="font-bold text-theme-primary underline underline-offset-4 hover:text-theme-primary/80">INITIATE PROTOCOL</router-link>
      </p>
      <p>
        > FORGOT PASSPHRASE:
        <router-link to="/forgot-password" class="font-bold text-theme-primary underline underline-offset-4 hover:text-theme-primary/80">RESET ACCESS</router-link>
      </p>
    </template>
  </AuthTerminalFrame>
</template>
