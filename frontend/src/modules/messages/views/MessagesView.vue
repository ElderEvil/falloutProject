<script setup lang="ts">
import { ref } from 'vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import VaultPageShell from '@/core/components/common/VaultPageShell.vue'
import ContactsPanel from '../components/ContactsPanel.vue'
import ConversationsPanel from '../components/ConversationsPanel.vue'

const activeTab = ref('conversations')
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

        <Tabs
          :model-value="activeTab"
          @update:model-value="(value) => (activeTab = String(value))"
        >
          <TabsList>
            <TabsTrigger value="conversations">Conversations</TabsTrigger>
            <TabsTrigger value="contacts">Contacts</TabsTrigger>
          </TabsList>

          <TabsContent value="conversations" class="py-2 text-base">
            <ConversationsPanel />
          </TabsContent>

          <TabsContent value="contacts" class="py-2 text-base">
            <ContactsPanel />
          </TabsContent>
        </Tabs>
      </PageContentRail>
    </VaultPageShell>
  </div>
</template>
