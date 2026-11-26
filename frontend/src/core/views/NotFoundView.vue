<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Button } from '@/core/components/ui/button'

const router = useRouter()
</script>

<template>
  <section
    class="relative min-h-screen bg-terminal-background p-6 font-mono text-theme-primary"
    aria-labelledby="not-found-title"
  >
    <div class="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p class="text-xs tracking-[0.3em] text-theme-primary/60 uppercase">Signal lost</p>
      <h1 id="not-found-title" class="terminal-glow text-3xl font-bold tracking-widest uppercase">
        404 — route not found
      </h1>
      <p class="max-w-sm text-xs leading-relaxed text-theme-primary/70">
        This terminal has no record of that address. The Overseer suggests heading back to the
        vault.
      </p>
      <Button variant="outline" size="sm" @click="router.push('/')">Return to the vault</Button>
    </div>
  </section>
</template>
