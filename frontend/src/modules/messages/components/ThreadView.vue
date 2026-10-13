<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { formatDateTime } from '@/core/utils/format'
import type { DirectMessageRead } from '../models/messages'

const props = defineProps<{
  messages: DirectMessageRead[]
  counterpartUsername: string
  isLoading: boolean
  isSending: boolean
}>()

const emit = defineEmits<{
  send: [body: string]
}>()

const authStore = useAuthStore()

const draft = ref('')
const scroller = ref<HTMLElement | null>(null)

const isMine = (message: DirectMessageRead) => message.sender_user_id === authStore.user?.id

const scrollToBottom = async () => {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

watch(
  () => props.messages.length,
  () => void scrollToBottom()
)

async function sendDraft() {
  const body = draft.value.trim()
  if (!body || props.isSending) return
  emit('send', body)
  draft.value = ''
  await scrollToBottom()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void sendDraft()
  }
}

const composerCount = computed(() => draft.value.trim().length)
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <header class="flex items-center justify-between border-b border-theme-primary/25 pb-3">
      <h2 class="m-0 text-base text-theme-primary terminal-glow">{{ counterpartUsername }}</h2>
      <span class="rounded border border-theme-primary/40 px-2 py-0.5 text-xs text-terminal-green-dim">
        DIRECT // {{ counterpartUsername.toUpperCase() }}
      </span>
    </header>

    <TerminalLoadingState v-if="isLoading" message="Loading messages..." />

    <div
      v-else-if="messages.length === 0"
      class="flex flex-1 items-center justify-center rounded-lg border-2 border-dashed border-theme-primary/30 p-8 text-center"
    >
      <p class="text-sm text-theme-primary/60">No messages yet. Say hello.</p>
    </div>

    <div
      v-else
      ref="scroller"
      class="flex max-h-96 min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-2"
      role="log"
      aria-live="polite"
    >
      <div
        v-for="message in messages"
        :key="message.id"
        class="flex flex-col"
        :class="isMine(message) ? 'items-end self-end' : 'items-start self-start'"
      >
        <div
          class="max-w-75 break-words rounded-lg border px-3 py-2 text-sm"
          :class="
            isMine(message)
              ? 'border-theme-primary/50 bg-theme-primary/15 text-terminal-green'
              : 'border-theme-primary/25 bg-surface-raised/60 text-theme-primary/90'
          "
        >
          <p class="m-0 whitespace-pre-wrap">{{ message.body }}</p>
          <p
            class="mt-1 text-[11px]"
            :class="isMine(message) ? 'text-terminal-green-dim' : 'text-theme-primary/50'"
          >
            {{ formatDateTime(message.created_at ?? '') }}
          </p>
        </div>
        <span
          v-if="message.is_request"
          class="mt-1 rounded border border-theme-accent/50 px-1 py-0.5 text-[10px] tracking-wider text-theme-accent"
        >
          FIRST MESSAGE (REQUEST)
        </span>
      </div>
    </div>

    <form class="flex items-end gap-2" @submit.prevent="sendDraft">
      <label class="sr-only" for="message-composer">Message {{ counterpartUsername }}</label>
      <textarea
        id="message-composer"
        v-model="draft"
        rows="2"
        maxlength="2000"
        class="min-h-14 flex-1 resize-none rounded-lg border-2 border-theme-primary/40 bg-terminal-background px-3 py-2 font-mono text-sm text-theme-primary outline-none placeholder:text-theme-primary/40 focus-visible:border-theme-primary"
        placeholder="Type a message…"
        @keydown="onKeydown"
      />
      <Button
        type="submit"
        size="sm"
        class="border-2 border-theme-primary hover:shadow-glow-md"
        :disabled="isSending || composerCount === 0"
        aria-label="Send message"
      >
        <Icon v-if="isSending" icon="mdi:loading" class="animate-spin" />
        <Icon v-else icon="mdi:send" class="h-4 w-4" />
      </Button>
    </form>
  </div>
</template>
