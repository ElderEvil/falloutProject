<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
</script>

<template>
  <NConfigProvider :theme-overrides="themeStore.themeOverrides">
    <NMessageProvider>
      <div
        class="terminal"
        :style="{
          '--theme-primary': themeStore.theme.colors.primary,
          '--theme-background': themeStore.theme.colors.background,
          '--theme-border': themeStore.theme.colors.border,
          '--theme-text': themeStore.theme.colors.text,
          '--theme-shadow': themeStore.theme.colors.shadow
        }"
      >
        <router-view></router-view>
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
.terminal {
  min-height: 100vh;
  background: var(--theme-background);
  position: relative;
}

.terminal * {
  text-shadow: 0 0 5px var(--theme-shadow);
}

.terminal button {
  text-shadow: 0 0 8px var(--theme-shadow);
}

.terminal h1,
.terminal h2,
.terminal h3 {
  text-shadow: 0 0 10px var(--theme-shadow);
}
</style>
