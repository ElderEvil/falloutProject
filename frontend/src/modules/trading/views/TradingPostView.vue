<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import TradingPostPanel from '../components/TradingPostPanel.vue'

const route = useRoute()

const vaultId = computed(() => route.params.id as string)
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Trading Post"
          icon="mdi:store"
          subtitle="Trade soft-deleted dwellers for bottle caps with other vaults"
        />

        <TradingPostPanel :vault-id="vaultId" />
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
