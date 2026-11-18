<script setup lang="ts">
import { inject, ref } from 'vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageContentRail from './PageContentRail.vue'
import SidePanel from './SidePanel.vue'

withDefaults(
  defineProps<{
    flicker?: boolean
    rail?: boolean
    sidePanel?: boolean
    vaultId?: string | null
    terminal?: boolean
  }>(),
  { flicker: false, rail: false, sidePanel: true, vaultId: null, terminal: false }
)

const { isCollapsed } = useSidePanel()
const isFlickeringEnabled = inject('isFlickering', ref(false))
</script>

<template>
  <div
    class="vault-page-shell vault-layout"
    :class="
      terminal ? 'relative min-h-screen bg-terminal-background font-mono text-terminal-green' : ''
    "
  >
    <SidePanel v-if="sidePanel" :vault-id="vaultId" />
    <main
      class="vault-page-main main-content min-w-0 flex-1 pb-8 leading-[1.6] transition-[margin-left] duration-300 ease max-md:ml-0"
      :class="[isCollapsed ? 'ml-16' : 'ml-60', { flicker: flicker && isFlickeringEnabled }]"
    >
      <PageContentRail v-if="rail">
        <slot />
      </PageContentRail>
      <slot v-else />
    </main>
  </div>
</template>

<style scoped>
.vault-page-shell {
  display: flex;
  min-height: 100vh;
}

.vault-page-main {
  font-weight: 700;
  letter-spacing: 0.025em;
}

.vault-page-main :deep(h1),
.vault-page-main :deep(h2),
.vault-page-main :deep(h3) {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}
</style>
