<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '../stores/auth'
import { oauthService, type OAuthProvider } from '../services/oauthService'
import { setLastAuthMethod } from '../utils/lastAuthMethod'
import AuthTerminalFrame from '../components/AuthTerminalFrame.vue'

const ERROR_MESSAGES: Record<string, string> = {
  state_invalid: 'Sign-in session expired or invalid. Please try again.',
  email_unverified: 'Your provider email is not verified.',
  email_verification_required:
    'This mailbox cannot be verified by the provider. Sign in with a password or use Gmail/Workspace.',
  local_account_unverified: 'This email already has an account. Sign in with your password.',
  account_exists_challenge: 'This email already has an account. Sign in with your password.',
  account_deleted: 'This account has been deleted.',
  account_inactive: 'This account is inactive.',
  provider_already_linked: 'This provider is already linked to another identity.',
  registration_closed: 'Open registration is disabled.',
  provider_disabled: 'This sign-in provider is not configured.',
  access_denied: 'Sign-in was cancelled.',
  handoff_invalid: 'Sign-in session expired. Please try again.',
  oauth_failed: 'Sign-in failed. Please try again.',
  provider_error: 'The sign-in provider rejected the request. Please try again.',
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const error = ref('')
const errorCode = ref('')
const isDev = import.meta.env.DEV

function queryValue(name: string): string | null {
  const value = route.query[name]
  return typeof value === 'string' ? value : null
}

onMounted(async () => {
  const queryError = queryValue('error')
  if (queryError) {
    errorCode.value = queryError
    error.value = ERROR_MESSAGES[queryError] ?? 'Sign-in failed. Please try again.'
    return
  }

  const code = queryValue('code')
  const providerValue = queryValue('provider')
  const provider: OAuthProvider | null =
    providerValue === 'google' || providerValue === 'github' ? providerValue : null

  window.history.replaceState(window.history.state, '', '/auth/callback')
  if (!code) {
    error.value = 'Sign-in failed: missing handoff code.'
    return
  }

  try {
    const response = await oauthService.redeemHandoff(code)
    const signedIn = await authStore.loginWithTokens(response.data)
    if (!signedIn) {
      error.value = 'Sign-in failed. Please try again.'
      return
    }
    if (provider) setLastAuthMethod(provider)
    await router.replace('/')
  } catch (cause) {
    const message = handleStoreError(cause, 'OAuth sign-in failed', false)
    console.error('[oauth] handoff redemption failed:', message)
    error.value = 'Sign-in failed. Please try again.'
  }
})
</script>

<template>
  <AuthTerminalFrame
    title="Vault Network Access Terminal"
    status="RESOLVING PROVIDER SESSION..."
    :error="error"
    error-detail="SIGN-IN FAILED - PLEASE TRY AGAIN"
  >
    <p v-if="errorCode && isDev" class="font-mono text-xs text-theme-primary/50">
      ERROR CODE: {{ errorCode }}
    </p>
    <p v-if="!error" class="font-mono text-sm leading-6 text-theme-primary/80">
      > Establishing secure channel to Vault-Tec authorisation services...
    </p>
    <template #links>
      <p>
        > RETURN TO ACCESS TERMINAL:
        <router-link
          to="/login"
          class="font-bold text-theme-primary underline underline-offset-4 hover:text-theme-primary/80"
        >
          RETRY
        </router-link>
      </p>
    </template>
  </AuthTerminalFrame>
</template>
