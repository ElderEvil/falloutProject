<script setup lang="ts">
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import ContactsPanel from '../components/ContactsPanel.vue'
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <VaultPageShell flicker>
      <PageContentRail class="flex flex-col gap-6">
        <PageHeader
          title="Messages"
          icon="mdi:message-text-outline"
          subtitle="Connect with other players and send direct messages"
        />

        <ContactsPanel />
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>