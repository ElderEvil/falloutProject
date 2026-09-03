<script setup lang="ts">
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from './SidePanel.vue'

withDefaults(defineProps<{ flicker?: boolean }>(), {
  flicker: false,
})

const { isCollapsed } = useSidePanel()
</script>

<template>
  <div class="vault-page-shell vault-layout">
    <SidePanel />
    <main class="vault-page-main main-content" :class="{ collapsed: isCollapsed, flicker }">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.vault-page-shell {
  display: flex;
  min-height: 100vh;
}

.vault-page-main {
  flex: 1;
  min-width: 0;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.vault-page-main.collapsed {
  margin-left: 64px;
}
</style>
