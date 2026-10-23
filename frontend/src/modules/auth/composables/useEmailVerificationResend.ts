import { computed, ref } from 'vue'
import { useAuthStore } from '../stores/auth'

export type EmailVerificationResendStatus = 'idle' | 'sending' | 'sent' | 'error'

export function useEmailVerificationResend() {
  const authStore = useAuthStore()
  const status = ref<EmailVerificationResendStatus>('idle')

  const label = computed(() => {
    if (status.value === 'sending') return 'SENDING...'
    if (status.value === 'sent') return 'EMAIL SENT'
    return 'RESEND EMAIL'
  })

  async function resend(): Promise<boolean> {
    if (status.value === 'sending') return false
    status.value = 'sending'
    const sent = await authStore.resendVerificationEmail()
    status.value = sent ? 'sent' : 'error'
    return sent
  }

  return { status, label, resend }
}
