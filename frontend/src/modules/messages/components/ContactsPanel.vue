<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { useToast } from '@/core/composables/useToast'
import { useMessagesStore } from '../stores/messages'

const store = useMessagesStore()
const toast = useToast()

const username = ref('')

async function sendInvite() {
  const trimmed = username.value.trim()
  if (!trimmed) return
  const result = await store.inviteByUsername(trimmed)
  if (result) {
    toast.success(`Invite sent to ${trimmed}`)
    username.value = ''
  }
}

onMounted(() => {
  void store.fetchContacts()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <TerminalLoadingState v-if="store.isLoading && store.connections.length === 0" message="Loading contacts..." />

    <div v-else-if="store.loadError" class="flex flex-col items-center gap-4 p-8">
      <p class="text-theme-primary/80">{{ store.loadError }}</p>
      <Button variant="outline" size="sm" class="border-2 border-theme-primary bg-transparent" @click="store.fetchContacts">
        <Icon icon="mdi:refresh" class="h-4 w-4" />
        Retry
      </Button>
    </div>

    <template v-else>
      <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
        <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
          <CardTitle class="text-base text-theme-primary terminal-glow">Invite Player</CardTitle>
        </CardHeader>
        <CardContent class="flex flex-col gap-3 p-4">
          <p class="text-sm text-theme-primary/70">Send a connection request to another player's exact username.</p>
          <form class="flex gap-2" @submit.prevent="sendInvite">
            <div class="flex flex-1 flex-col gap-1">
              <Label for="invite-username" class="text-xs text-theme-primary/75">Username</Label>
              <Input
                id="invite-username"
                v-model="username"
                class="border-2 border-theme-primary/40 bg-terminal-background font-mono text-theme-primary placeholder:text-theme-primary/40"
                placeholder="username"
                maxlength="32"
                autocomplete="off"
              />
            </div>
            <Button
              type="submit"
              size="sm"
              class="mt-5 self-end border-2 border-theme-primary hover:shadow-glow-md"
              :disabled="store.isInviting || username.trim() === ''"
            >
              <Icon v-if="store.isInviting" icon="mdi:loading" class="animate-spin" />
              <Icon v-else icon="mdi:account-plus" class="h-4 w-4" />
              Invite
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
        <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
          <CardTitle class="text-base text-theme-primary terminal-glow">Incoming Requests</CardTitle>
        </CardHeader>
        <CardContent class="p-4">
          <ul v-if="store.incomingRequests.length > 0" class="flex flex-col gap-2">
            <li
              v-for="connection in store.incomingRequests"
              :key="connection.id"
              class="flex items-center justify-between gap-3 rounded-lg border border-theme-primary/25 bg-surface-raised/60 px-3 py-2"
            >
              <span class="font-mono text-sm text-theme-primary">{{ connection.counterpart_username }}</span>
              <span class="flex gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  class="border-2 border-theme-primary bg-transparent"
                  :disabled="store.busyUserId === connection.id"
                  @click="store.acceptConnection(connection.id)"
                >
                  <Icon v-if="store.busyUserId === connection.id" icon="mdi:loading" class="animate-spin" />
                  Accept
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  class="border-theme-primary bg-transparent text-theme-accent"
                  :disabled="store.busyUserId === connection.id"
                  @click="store.declineConnection(connection.id)"
                >
                  Decline
                </Button>
              </span>
            </li>
          </ul>
          <p v-else class="text-sm text-theme-primary/60">No pending requests.</p>
        </CardContent>
      </Card>

      <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
        <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
          <CardTitle class="text-base text-theme-primary terminal-glow">Outgoing Requests</CardTitle>
        </CardHeader>
        <CardContent class="p-4">
          <ul v-if="store.outgoingRequests.length > 0" class="flex flex-col gap-2">
            <li
              v-for="connection in store.outgoingRequests"
              :key="connection.id"
              class="flex items-center justify-between gap-3 rounded-lg border border-theme-primary/25 bg-surface-raised/60 px-3 py-2"
            >
              <span class="font-mono text-sm text-theme-primary">{{ connection.counterpart_username }}</span>
              <Button
                variant="outline"
                size="xs"
                class="border-theme-primary bg-transparent text-theme-accent"
                :disabled="store.busyUserId === connection.id"
                @click="store.revokeConnection(connection.id)"
              >
                <Icon v-if="store.busyUserId === connection.id" icon="mdi:loading" class="animate-spin" />
                Revoke
              </Button>
            </li>
          </ul>
          <p v-else class="text-sm text-theme-primary/60">No pending requests.</p>
        </CardContent>
      </Card>

      <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
        <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
          <CardTitle class="text-base text-theme-primary terminal-glow">Connections</CardTitle>
        </CardHeader>
        <CardContent class="p-4">
          <ul v-if="store.acceptedConnections.length > 0" class="flex flex-col gap-2">
            <li
              v-for="connection in store.acceptedConnections"
              :key="connection.id"
              class="flex items-center justify-between gap-3 rounded-lg border border-theme-primary/25 bg-surface-raised/60 px-3 py-2"
            >
              <span class="font-mono text-sm text-terminal-green">{{ connection.counterpart_username }}</span>
              <Button
                variant="outline"
                size="xs"
                class="border-theme-primary bg-transparent text-theme-accent"
                :disabled="store.busyUserId === store.counterpartId(connection)"
                @click="store.blockUser(store.counterpartId(connection))"
              >
                <Icon v-if="store.busyUserId === store.counterpartId(connection)" icon="mdi:loading" class="animate-spin" />
                <Icon icon="mdi:block-helper" class="h-3 w-3" />
                Block
              </Button>
            </li>
          </ul>
          <p v-else class="text-sm text-theme-primary/60">No connections yet. Invite a player to get started.</p>
        </CardContent>
      </Card>

      <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
        <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
          <CardTitle class="text-base text-theme-primary terminal-glow">Blocked Users</CardTitle>
        </CardHeader>
        <CardContent class="p-4">
          <ul v-if="store.blocks.length > 0" class="flex flex-col gap-2">
            <li
              v-for="block in store.blocks"
              :key="block.id"
              class="flex items-center justify-between gap-3 rounded-lg border border-theme-primary/25 bg-surface-raised/60 px-3 py-2"
            >
              <span class="font-mono text-sm text-terminal-green-dim">{{ block.blocked_username }}</span>
              <Button
                variant="outline"
                size="xs"
                class="border-theme-primary bg-transparent"
                :disabled="store.busyUserId === block.blocked_id"
                @click="store.unblockUser(block.blocked_id)"
              >
                <Icon v-if="store.busyUserId === block.blocked_id" icon="mdi:loading" class="animate-spin" />
                Unblock
              </Button>
            </li>
          </ul>
          <p v-else class="text-sm text-theme-primary/60">No blocked users.</p>
        </CardContent>
      </Card>
    </template>
  </div>
</template>