<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import {
  oauthService,
  type OAuthLinkedAccounts,
  type OAuthProvider,
  type OAuthProviders,
} from '@/modules/auth/services/oauthService'

const PROVIDER_ICONS: Record<OAuthProvider, string> = {
  google: 'mdi:google',
  github: 'mdi:github',
}

const ERROR_MESSAGES: Record<string, string> = {
  provider_identity_in_use:
    'That provider is already connected to another account. Ask an administrator to merge the accounts.',
  provider_already_linked: 'That provider is already connected to your account.',
  provider_not_linked: 'That provider is not connected.',
  last_sign_in_method: 'You cannot remove your only sign-in method. Set a password first.',
  provider_disabled: 'That sign-in provider is not available.',
}

const props = withDefaults(defineProps<{ navigate?: (url: string) => void }>(), {
  navigate: (url: string) => window.location.assign(url),
})
const toast = useToast()
const providers = ref<OAuthProviders>({ google: false, github: false })
const linkedProviders = ref<OAuthProvider[]>([])
const hasPassword = ref(true)
const loading = ref(true)
const loadError = ref('')
const busyProvider = ref<OAuthProvider | null>(null)
const confirmingProvider = ref<OAuthProvider | null>(null)

const allProviders = computed<OAuthProvider[]>(() =>
  (['google', 'github'] as OAuthProvider[]).filter(
    (provider) => providers.value[provider] || linkedProviders.value.includes(provider)
  )
)
const canUnlink = computed(() => hasPassword.value || linkedProviders.value.length > 1)

const isLinked = (provider: OAuthProvider) => linkedProviders.value.includes(provider)
const isEnabled = (provider: OAuthProvider) => providers.value[provider]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const [enabled, accounts]: [OAuthProviders, OAuthLinkedAccounts] = await Promise.all([
      oauthService.getProviders(),
      oauthService.getLinkedAccounts(),
    ])
    providers.value = enabled
    linkedProviders.value = accounts.providers
    hasPassword.value = accounts.has_password
  } catch (error) {
    loadError.value = getErrorMessage(error)
    handleStoreError(error, 'Could not load connected accounts', false)
  } finally {
    loading.value = false
  }
}

async function link(provider: OAuthProvider): Promise<void> {
  if (busyProvider.value) return
  busyProvider.value = provider
  try {
    const { authorize_url } = await oauthService.linkProvider(provider)
    props.navigate(authorize_url)
  } catch (error) {
    const message = getErrorMessage(error)
    handleStoreError(error, 'Could not start provider link', false)
    toast.error(ERROR_MESSAGES[message] ?? message)
  } finally {
    busyProvider.value = null
  }
}

function askUnlink(provider: OAuthProvider): void {
  confirmingProvider.value = provider
}

function cancelUnlink(): void {
  confirmingProvider.value = null
}

async function confirmUnlink(provider: OAuthProvider): Promise<void> {
  if (busyProvider.value) return
  busyProvider.value = provider
  try {
    await oauthService.unlinkProvider(provider)
    linkedProviders.value = linkedProviders.value.filter((item) => item !== provider)
    confirmingProvider.value = null
    toast.success(`${provider.toUpperCase()} disconnected`)
  } catch (error) {
    const message = getErrorMessage(error)
    handleStoreError(error, 'Could not disconnect provider', false)
    toast.error(ERROR_MESSAGES[message] ?? message)
  } finally {
    busyProvider.value = null
  }
}

onMounted(load)
</script>

<template>
  <Card class="connected-accounts gap-0 border-theme-primary/20 bg-surface">
    <CardHeader class="pb-2">
      <CardTitle class="text-lg font-bold text-theme-primary">Connected accounts</CardTitle>
    </CardHeader>
    <CardContent class="pt-0">
      <p class="text-xs leading-5 text-theme-primary/60">
        Connect a provider to sign in with it. Linking never moves vaults or progress; ask an
        administrator to merge duplicate accounts.
      </p>

      <div v-if="loading" class="py-6 text-center text-sm text-theme-primary/60">
        Loading connected accounts...
      </div>
      <p v-else-if="loadError" class="mt-4 text-sm text-danger">{{ loadError }}</p>
      <p v-else-if="!allProviders.length" class="mt-4 text-sm text-theme-primary/60">
        No provider sign-in is configured for this deployment.
      </p>
      <div v-else class="mt-3 grid gap-2 sm:grid-cols-2">
        <div
          v-for="provider in allProviders"
          :key="provider"
          class="flex items-center justify-between gap-2 rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2"
          v-bind="{ 'data-testid': `connected-${provider}` }"
        >
          <div class="flex min-w-0 items-center gap-2">
            <Icon :icon="PROVIDER_ICONS[provider]" class="h-5 w-5 shrink-0 text-theme-primary" />
            <div class="min-w-0">
              <p class="text-xs font-bold tracking-wide text-theme-primary">
                {{ provider.toUpperCase() }}
              </p>
              <p class="text-[0.65rem] text-theme-primary/60">
                {{
                  isLinked(provider)
                    ? 'CONNECTED'
                    : isEnabled(provider)
                      ? 'NOT CONNECTED'
                      : 'UNAVAILABLE'
                }}
              </p>
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-1">
            <template v-if="isLinked(provider)">
              <template v-if="confirmingProvider === provider">
                <span class="text-[0.6rem] font-bold tracking-wider text-warning">DISCONNECT?</span>
                <Button
                  size="xs"
                  variant="destructive"
                  :disabled="busyProvider === provider"
                  @click="confirmUnlink(provider)"
                >
                  CONFIRM
                </Button>
                <Button size="xs" variant="outline" @click="cancelUnlink">CANCEL</Button>
              </template>
              <Button
                v-else
                size="xs"
                variant="outline"
                :disabled="!canUnlink || busyProvider === provider"
                @click="askUnlink(provider)"
              >
                DISCONNECT
              </Button>
            </template>
            <Button
              v-else
              size="xs"
              variant="outline"
              :disabled="!isEnabled(provider) || busyProvider === provider"
              @click="link(provider)"
            >
              CONNECT
            </Button>
          </div>
        </div>

        <p v-if="!canUnlink" class="text-xs leading-5 text-warning sm:col-span-2">
          This is your only sign-in method. Set a password before disconnecting it.
        </p>
        <p class="text-xs text-theme-primary/50 sm:col-span-2">
          Password sign-in: {{ hasPassword ? 'enabled' : 'not set' }}.
        </p>
      </div>
    </CardContent>
  </Card>
</template>
