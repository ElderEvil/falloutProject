<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { formatDateTime } from '@/core/utils/format'
import { useMessagesStore } from '../stores/messages'
import ThreadView from './ThreadView.vue'

const store = useMessagesStore()

const plainConversations = computed(() =>
  store.conversations.filter((c) => !c.has_pending_request)
)

const preview = (body: string) => (body.length > 60 ? `${body.slice(0, 60)}…` : body)

function onWindowFocus() {
  void store.loadConversations()
}

onMounted(() => {
  void store.loadConversations()
  window.addEventListener('focus', onWindowFocus)
})

onUnmounted(() => {
  window.removeEventListener('focus', onWindowFocus)
  store.closeThread()
})

function openThread(userId: string) {
  void store.openThread(userId)
}
</script>

<template>
  <div class="grid min-h-0 gap-6 lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)]">
    <aside class="flex min-h-0 flex-col gap-6">
      <TerminalLoadingState
        v-if="store.isLoadingConversations && store.conversations.length === 0"
        message="Loading conversations..."
      />

      <div v-else-if="store.loadError" class="flex flex-col items-center gap-4 p-4">
        <p class="text-theme-primary/80">{{ store.loadError }}</p>
        <Button
          variant="outline"
          size="sm"
          class="border-2 border-theme-primary bg-transparent"
          @click="store.loadConversations"
        >
          <Icon icon="mdi:refresh" class="h-4 w-4" />
          Retry
        </Button>
      </div>

      <template v-else>
        <Card v-if="store.messageRequests.length > 0" class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
          <CardHeader class="border-b border-theme-accent/40 bg-theme-primary/5 p-4">
            <CardTitle class="text-base text-theme-accent terminal-glow">Message Requests</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-2 p-4">
            <div
              v-for="conversation in store.messageRequests"
              :key="conversation.counterpart_user_id"
              class="flex flex-col gap-2 rounded-lg border border-theme-accent/40 bg-surface-raised/60 px-3 py-2"
            >
              <button
                type="button"
                class="flex flex-col items-start gap-1 text-left"
                @click="openThread(conversation.counterpart_user_id)"
              >
                <span class="font-mono text-sm text-theme-accent">
                  {{ conversation.counterpart_username }}
                </span>
                <span class="text-xs text-theme-primary/70">wants to message you</span>
              </button>
              <span class="flex gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  class="border-2 border-theme-primary bg-transparent"
                  :disabled="store.busyUserId === conversation.counterpart_user_id"
                  @click="store.acceptMessageRequest(conversation.counterpart_user_id)"
                >
                  <Icon v-if="store.busyUserId === conversation.counterpart_user_id" icon="mdi:loading" class="animate-spin" />
                  Accept
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  class="border-theme-primary bg-transparent text-theme-accent"
                  :disabled="store.busyUserId === conversation.counterpart_user_id"
                  @click="store.declineMessageRequest(conversation.counterpart_user_id)"
                >
                  Decline
                </Button>
              </span>
            </div>
          </CardContent>
        </Card>

        <Card class="gap-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40">
          <CardHeader class="border-b border-theme-primary/25 bg-theme-primary/5 p-4">
            <CardTitle class="text-base text-theme-primary terminal-glow">Conversations</CardTitle>
          </CardHeader>
          <CardContent class="max-h-96 overflow-y-auto p-4 lg:max-h-[calc(100vh-19rem)]">
            <ul v-if="plainConversations.length > 0" class="flex flex-col gap-2">
              <li v-for="conversation in plainConversations" :key="conversation.counterpart_user_id">
                <button
                  type="button"
                  class="flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors"
                  :class="
                    store.activeThreadUserId === conversation.counterpart_user_id
                      ? 'border-theme-primary/70 bg-theme-primary/15'
                      : 'border-theme-primary/25 bg-surface-raised/60 hover:border-theme-primary/50'
                  "
                  :aria-current="
                    store.activeThreadUserId === conversation.counterpart_user_id ? 'true' : undefined
                  "
                  @click="openThread(conversation.counterpart_user_id)"
                >
                  <span class="flex items-center justify-between gap-2">
                    <span class="font-mono text-sm text-terminal-green">
                      {{ conversation.counterpart_username }}
                    </span>
                    <span v-if="conversation.unread_count > 0" class="text-xs">
                      <span
                        class="rounded-full border border-theme-primary/50 bg-theme-primary/20 px-2 py-0.5 font-bold text-theme-primary"
                      >
                        {{ conversation.unread_count }}
                      </span>
                    </span>
                  </span>
                  <span class="flex items-center justify-between gap-2 text-xs text-theme-primary/60">
                    <span class="truncate">{{ preview(conversation.last_message.body) }}</span>
                    <time class="shrink-0">
                      {{ formatDateTime(conversation.last_message.created_at ?? '') }}
                    </time>
                  </span>
                </button>
              </li>
            </ul>
            <p v-else class="text-sm text-theme-primary/60">
              No conversations yet. Invite a player from the Contacts tab.
            </p>
          </CardContent>
        </Card>
      </template>
    </aside>

    <section class="min-h-0 rounded-lg border-2 border-theme-primary/25 bg-surface-sunken/40 p-4">
      <ThreadView
        v-if="store.activeConversation"
        :messages="store.thread"
        :counterpart-username="store.activeConversation.counterpart_username"
        :is-loading="store.isLoadingThread"
        :is-sending="store.isSending"
        @send="store.sendMessage"
      />
      <div
        v-else
        class="flex h-full min-h-64 flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-theme-primary/30 p-8 text-center"
      >
        <Icon icon="mdi:message-text-outline" class="h-12 w-12 text-theme-primary/30" />
        <p class="text-sm text-theme-primary/70">Select a conversation to read messages</p>
      </div>
    </section>
  </div>
</template>
