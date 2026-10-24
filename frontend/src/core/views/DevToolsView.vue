<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()
const menus = computed(() =>
  router
    .getRoutes()
    .filter((route) => route.path.startsWith('/dev/') && typeof route.meta.devTitle === 'string')
    .map((route) => ({
      path: route.path,
      title: String(route.meta.devTitle),
      description: String(route.meta.devDescription),
    }))
    .sort((a, b) => a.title.localeCompare(b.title))
)
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
    <header class="space-y-2">
      <h1 class="text-3xl font-bold text-theme-primary">Development tools</h1>
      <p class="text-sm text-theme-primary/60">
        Visual previews and test menus. Available in development builds.
      </p>
    </header>
    <nav aria-label="Development menus" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <RouterLink
        v-for="menu in menus"
        :key="menu.path"
        :to="menu.path"
        class="group rounded-lg border border-theme-glow bg-surface p-5 transition-colors hover:border-theme-primary focus-visible:outline-2 focus-visible:outline-theme-primary"
      >
        <h2 class="text-lg font-semibold text-theme-primary">{{ menu.title }}</h2>
        <p class="mt-2 text-sm leading-relaxed text-theme-primary/60">{{ menu.description }}</p>
        <span class="mt-4 block text-xs text-theme-primary/70">{{ menu.path }} →</span>
      </RouterLink>
    </nav>
  </div>
</template>
