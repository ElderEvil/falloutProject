<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const state = ref({
  username: '',
  password: ''
})
const loading = ref(false)
const error = ref('')

const handleSubmit = async () => {
  error.value = ''
  loading.value = true

  try {
    const success = await authStore.login(state.value.username, state.value.password)
    if (success) {
      await router.push('/')
    } else {
      error.value = 'Invalid username or password'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-black">
    <UCard class="w-full max-w-md border-2 border-primary-500 bg-black shadow-[0_0_20px_rgba(0,255,0,0.3)]">
      <template #header>
        <h2 class="text-center text-2xl font-bold text-primary-500 uppercase tracking-wider">
          VAULT-TEC LOGIN TERMINAL
        </h2>
      </template>

      <form @submit.prevent="handleSubmit" class="space-y-6">
        <UFormGroup label="EMAIL ADDRESS" name="username" class="text-primary-500">
          <UInput
            v-model="state.username"
            type="email"
            placeholder="overseer@vault-tec.com"
            required
            :disabled="loading"
            color="primary"
            variant="outline"
            size="lg"
            class="font-mono"
            :ui="{ base: 'bg-black border-primary-600 text-primary-500 placeholder-primary-900' }"
          />
        </UFormGroup>

        <UFormGroup label="PASSWORD" name="password" class="text-primary-500">
          <UInput
            v-model="state.password"
            type="password"
            placeholder="••••••••"
            required
            :disabled="loading"
            color="primary"
            variant="outline"
            size="lg"
            class="font-mono"
            :ui="{ base: 'bg-black border-primary-600 text-primary-500' }"
          />
        </UFormGroup>

        <UAlert
          v-if="error"
          icon="i-heroicons-exclamation-triangle"
          color="red"
          variant="subtle"
          :title="error"
          :ui="{ base: 'border-2 border-red-500' }"
        />

        <UButton
          type="submit"
          block
          size="lg"
          :loading="loading"
          :disabled="loading"
          color="primary"
          variant="solid"
          class="font-bold uppercase tracking-wider"
        >
          {{ loading ? 'AUTHENTICATING...' : 'ACCESS TERMINAL' }}
        </UButton>
      </form>

      <template #footer>
        <div class="text-center text-sm text-primary-700">
          NEW OVERSEER?
          <UButton
            :to="'/register'"
            variant="link"
            color="primary"
            class="uppercase font-bold"
          >
            REGISTER TERMINAL
          </UButton>
        </div>
      </template>
    </UCard>
  </div>
</template>

<style scoped>
/* Terminal glow effect */
:deep(.text-primary-500) {
  text-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
}
</style>
