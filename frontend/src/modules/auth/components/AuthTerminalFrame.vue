<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Alert } from '@/core/components/ui/alert'
import { Card, CardContent, CardFooter, CardHeader } from '@/core/components/ui/card'
import { useVisualEffects } from '@/core/composables/useVisualEffects'

defineProps<{
  title: string
  status: string
  error?: string
  errorDetail?: string
}>()

const { flickering } = useVisualEffects()
const appVersion = __APP_VERSION__
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-terminal-background px-4 py-8 font-mono text-theme-primary">
    <Card
      class="w-full max-w-lg gap-0 border-2 border-theme-primary/60 bg-surface-sunken py-0 shadow-glow-md"
      :class="{ flicker: flickering }"
    >
      <CardHeader class="border-b border-theme-primary/30 px-6 py-6 text-center sm:px-8">
        <p class="text-[0.65rem] font-bold tracking-[0.2em] text-theme-primary/60">VAULT-TEC // SECURE ACCESS</p>
        <div class="flex items-center justify-center gap-3">
          <Icon icon="mdi:shield-lock-outline" class="size-8 shrink-0 text-theme-primary" :ariaHidden="true" />
          <h1 class="text-xl font-bold tracking-[0.08em] text-theme-primary terminal-glow sm:text-2xl">VAULT-TEC INDUSTRIES</h1>
        </div>
        <p class="text-xs uppercase tracking-[0.12em] text-theme-primary/70">{{ title }}</p>
      </CardHeader>

      <CardContent class="px-6 py-6 sm:px-8">
        <div class="system-messages mb-6 border-l-2 border-theme-primary/70 bg-surface px-4 py-3 text-xs leading-6 text-theme-primary/75">
          <p>> SECURE TERMINAL v{{ appVersion }}</p>
          <p>> {{ status }}</p>
        </div>

        <slot />

        <Alert v-if="error" variant="destructive" class="mt-5 border-danger/60 bg-danger/10 text-danger">
          <p>> ERROR: {{ error.toUpperCase() }}</p>
          <p v-if="errorDetail">> {{ errorDetail }}</p>
        </Alert>
      </CardContent>

      <CardFooter class="flex flex-col gap-4 border-t border-theme-primary/20 px-6 py-5 text-center sm:px-8">
        <nav class="flex flex-col gap-2 text-xs leading-5 text-theme-primary/80">
          <slot name="links" />
        </nav>
        <p class="text-[0.65rem] uppercase tracking-[0.08em] text-theme-primary/50">
          VAULT-TEC © 2077 • PROTECTING AMERICA'S FUTURE
        </p>
      </CardFooter>
    </Card>
  </main>
</template>
