<script setup lang="ts">
import { inject, ref } from 'vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import SidePanel from '@/core/components/common/SidePanel.vue'
import DwellerDetailContainer from '../components/DwellerDetailContainer.vue'

const scanlinesEnabled = inject('scanlines', ref(true))
const { isCollapsed } = useSidePanel()
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div v-if="scanlinesEnabled" class="scanlines" />

    <div class="vault-layout">
      <SidePanel />

      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8">
          <DwellerDetailContainer />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}
</style>
