<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { Button } from '@/core/components/ui/button'
import AuthTerminalFrame from '../components/AuthTerminalFrame.vue'
import { useAuthStore } from '../stores/auth'
import { useEmailVerificationResend } from '../composables/useEmailVerificationResend'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { status: resendStatus, label: resendLabel, resend } = useEmailVerificationResend()

const token = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(true)

const canResend = computed(
  () => authStore.isAuthenticated && authStore.user?.email_verified === false
)

const status = computed(() => {
  if (loading.value) return 'PROCESSING VERIFICATION TOKEN...'
  return success.value ? 'VERIFICATION SUCCESSFUL' : 'VERIFICATION FAILED'
})

async function verifyEmail(verificationToken: string): Promise<void> {
  const verified = await authStore.verifyEmail(verificationToken)
  if (!verified) {
    error.value = 'The verification link is invalid or has expired'
    return
  }
  success.value = true
  await router.push(authStore.isAuthenticated ? '/' : '/login')
}

onMounted(async () => {
  token.value = (route.query.token as string) || ''

  if (!token.value) {
    error.value = 'Invalid or missing verification token'
    loading.value = false
    return
  }

  try {
    await verifyEmail(token.value)
  } catch (err) {
    error.value = getErrorMessage(err, 'Failed to verify email')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <AuthTerminalFrame title="Email Verification Terminal" :status="status">
    <p v-if="loading" class="text-sm leading-6">> PROCESSING VERIFICATION TOKEN...</p>

    <div v-else-if="success" class="space-y-2 text-sm leading-6">
      <p>> STATUS: VERIFICATION SUCCESSFUL</p>
      <p>> YOUR EMAIL HAS BEEN VERIFIED</p>
      <p>> REDIRECTING...</p>
    </div>

    <div v-else-if="error" class="space-y-2 text-sm leading-6">
      <p class="text-danger">> ERROR: VERIFICATION FAILED</p>
      <p class="text-danger">{{ error }}</p>
      <div class="mt-6 flex flex-wrap gap-3">
        <Button
          v-if="canResend"
          variant="default"
          class="border-2 border-theme-primary hover:shadow-glow-md"
          :disabled="resendStatus === 'sending'"
          @click="resend"
        >
          {{ resendLabel }}
        </Button>
        <Button
          variant="default"
          class="border-2 border-theme-primary hover:shadow-glow-md"
          @click="router.push('/login')"
        >
          RETURN TO LOGIN
        </Button>
      </div>
      <p v-if="resendStatus === 'error'" class="text-danger">> RESEND FAILED - TRY AGAIN LATER</p>
    </div>

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
