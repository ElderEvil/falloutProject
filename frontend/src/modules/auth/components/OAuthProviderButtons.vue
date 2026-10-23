<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Button } from '@/core/components/ui/button'
import { handleStoreError } from '@/core/utils/errorHandler'
import { oauthService, type OAuthProvider } from '../services/oauthService'
import { getLastAuthMethod, type AuthMethod } from '../utils/lastAuthMethod'

withDefaults(defineProps<{ label?: string }>(), { label: 'OR AUTHENTICATE WITH' })

const providers = ref<Record<OAuthProvider, boolean>>({ google: false, github: false })
const lastMethod = ref<AuthMethod | null>(getLastAuthMethod())
const enabledProviders = computed<OAuthProvider[]>(() =>
  (['google', 'github'] as OAuthProvider[]).filter((provider) => providers.value[provider])
)

onMounted(async () => {
  try {
    providers.value = await oauthService.getProviders()
  } catch (error) {
    const message = handleStoreError(error, 'OAuth provider discovery failed', false)
    console.error('[oauth] provider discovery failed:', message)
  }
})

const startOAuth = (provider: OAuthProvider) => {
  window.location.assign(oauthService.authorizeUrl(provider))
}
</script>

<template>
  <div v-if="enabledProviders.length" class="mt-5 flex flex-col gap-3 border-t border-theme-primary/30 pt-5">
    <p class="text-center font-mono text-xs tracking-widest text-theme-primary/60">— {{ label }} —</p>
    <Button
      v-for="provider in enabledProviders"
      :key="provider"
      type="button"
      variant="outline"
      class="relative w-full border-theme-primary"
      @click="startOAuth(provider)"
    >
      <span class="w-full text-center">CONTINUE WITH {{ provider.toUpperCase() }}</span>
      <span
        v-if="lastMethod === provider"
        class="absolute right-2 border border-theme-primary/50 px-1 py-0.5 text-[9px] tracking-widest"
      >
        LAST USED
      </span>
    </Button>
  </div>
</template>
