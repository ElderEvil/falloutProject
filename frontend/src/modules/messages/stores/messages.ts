import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import { handleStoreError } from '@/core/utils/errorHandler'
import { messagesService } from '../services/messagesService'
import type {
  ConnectionRead,
  DirectMessageRead,
  DirectMessageSummary,
  UserBlockRead,
} from '../models/messages'

/** Poll cadence for the open thread; there is no per-user WS channel yet. */
export const THREAD_POLL_INTERVAL_MS = 5000

/**
 * Player-to-player messaging (connections, blocks, direct messages). Every
 * action no-ops while the `player_connections` feature flag is off, so the
 * store can ship dead-simple and stay off until the backend enables it.
 */
export const useMessagesStore = defineStore('messages', () => {
  const featureFlags = useFeatureFlagsStore()
  const authStore = useAuthStore()

  const connections = ref<ConnectionRead[]>([])
  const blocks = ref<UserBlockRead[]>([])
  const conversations = ref<DirectMessageSummary[]>([])
  const thread = ref<DirectMessageRead[]>([])
  const activeThreadUserId = ref<string | null>(null)
  const isLoading = ref(false)
  const isLoadingConversations = ref(false)
  const isLoadingThread = ref(false)
  const isInviting = ref(false)
  const isSending = ref(false)
  const busyUserId = ref<string | null>(null)
  const loadError = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  const enabled = computed(() => featureFlags.playerConnections)
  const me = computed(() => authStore.user?.id ?? null)
  const incomingRequests = computed(() =>
    connections.value.filter((c) => c.status === 'pending' && c.addressee_id === me.value)
  )
  const outgoingRequests = computed(() =>
    connections.value.filter((c) => c.status === 'pending' && c.requester_id === me.value)
  )
  const acceptedConnections = computed(() => connections.value.filter((c) => c.status === 'accepted'))
  const activeConversation = computed(
    () =>
      conversations.value.find((c) => c.counterpart_user_id === activeThreadUserId.value) ?? null
  )
  const messageRequests = computed(() =>
    conversations.value.filter((c) => c.has_pending_request)
  )

  function ready(): boolean {
    return enabled.value && Boolean(authStore.token)
  }

  function counterpartId(connection: ConnectionRead): string {
    return me.value === connection.requester_id
      ? connection.addressee_id
      : connection.requester_id
  }

  function quietError(error: unknown, context: string): null {
    loadError.value = handleStoreError(error, context, false)
    return null
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function refreshOpenThread(): Promise<void> {
    const userId = activeThreadUserId.value
    if (!ready() || !authStore.token || !userId) return
    try {
      const [rows, summaryRows] = await Promise.all([
        messagesService.getThread(userId, authStore.token),
        messagesService.listConversations(authStore.token),
      ])
      thread.value = rows
      conversations.value = summaryRows
    } catch (error) {
      handleStoreError(error, 'Live messages refresh failed', false)
    }
  }

  function startPolling(): void {
    stopPolling()
    pollTimer = setInterval(() => void refreshOpenThread(), THREAD_POLL_INTERVAL_MS)
  }

  async function fetchContacts() {
    if (!ready() || !authStore.token) return null
    isLoading.value = true
    loadError.value = null
    try {
      const [connectionRows, blockRows] = await Promise.all([
        messagesService.listConnections(authStore.token),
        messagesService.listBlocks(authStore.token),
      ])
      connections.value = connectionRows
      blocks.value = blockRows
    } catch (error) {
      return quietError(error, 'Failed to load contacts')
    } finally {
      isLoading.value = false
    }
  }

  async function inviteByUsername(username: string) {
    if (!ready() || !authStore.token) return null
    isInviting.value = true
    try {
      const connection = await messagesService.inviteByUsername(username, authStore.token)
      await fetchContacts()
      return connection
    } catch (error) {
      handleStoreError(error, 'Failed to send invite')
    } finally {
      isInviting.value = false
    }
  }

  async function acceptConnection(connectionId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = connectionId
    try {
      const connection = await messagesService.acceptConnection(connectionId, authStore.token)
      await fetchContacts()
      return connection
    } catch (error) {
      handleStoreError(error, 'Failed to accept connection request')
    } finally {
      busyUserId.value = null
    }
  }

  async function declineConnection(connectionId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = connectionId
    try {
      await messagesService.declineConnection(connectionId, authStore.token)
      await fetchContacts()
    } catch (error) {
      handleStoreError(error, 'Failed to decline connection request')
    } finally {
      busyUserId.value = null
    }
  }

  async function revokeConnection(connectionId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = connectionId
    try {
      await messagesService.revokeConnection(connectionId, authStore.token)
      await fetchContacts()
    } catch (error) {
      handleStoreError(error, 'Failed to revoke connection')
    } finally {
      busyUserId.value = null
    }
  }

  async function blockUser(userId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = userId
    try {
      await messagesService.blockUser(userId, authStore.token)
      await fetchContacts()
    } catch (error) {
      handleStoreError(error, 'Failed to block user')
    } finally {
      busyUserId.value = null
    }
  }

async function unblockUser(userId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = userId
    try {
      await messagesService.unblockUser(userId, authStore.token)
      await fetchContacts()
    } catch (error) {
      return quietError(error, 'Failed to unblock user')
    } finally {
      busyUserId.value = null
    }
  }

  async function loadConversations() {
    if (!ready() || !authStore.token) return null
    isLoadingConversations.value = true
    try {
      conversations.value = await messagesService.listConversations(authStore.token)
    } catch (error) {
      return quietError(error, 'Failed to load conversations')
    } finally {
      isLoadingConversations.value = false
    }
  }

  async function openThread(userId: string) {
    if (!ready() || !authStore.token) return null
    activeThreadUserId.value = userId
    isLoadingThread.value = true
    try {
      thread.value = await messagesService.getThread(userId, authStore.token)
      startPolling()
    } catch (error) {
      return quietError(error, 'Failed to load messages')
    } finally {
      isLoadingThread.value = false
    }
  }

  function closeThread(): void {
    stopPolling()
    activeThreadUserId.value = null
    thread.value = []
  }

  async function sendMessage(body: string) {
    const userId = activeThreadUserId.value
    if (!ready() || !authStore.token || !userId) return null
    isSending.value = true
    try {
      const message = await messagesService.sendMessage(userId, body, authStore.token)
      thread.value.push(message)
      return message
    } catch (error) {
      handleStoreError(error, 'Failed to send message')
      return null
    } finally {
      isSending.value = false
    }
  }

  async function acceptMessageRequest(userId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = userId
    try {
      await messagesService.acceptMessageRequest(userId, authStore.token)
      await Promise.all([loadConversations(), fetchContacts()])
    } catch (error) {
      return quietError(error, 'Failed to accept message request')
    } finally {
      busyUserId.value = null
    }
  }

  async function declineMessageRequest(userId: string) {
    if (!ready() || !authStore.token) return null
    busyUserId.value = userId
    try {
      await messagesService.declineMessageRequest(userId, authStore.token)
      await loadConversations()
    } catch (error) {
      return quietError(error, 'Failed to decline message request')
    } finally {
      busyUserId.value = null
    }
  }

  return {
    connections,
    blocks,
    conversations,
    thread,
    activeThreadUserId,
    isLoading,
    isLoadingConversations,
    isLoadingThread,
    isInviting,
    isSending,
    busyUserId,
    loadError,
    enabled,
    me,
    counterpartId,
    incomingRequests,
    outgoingRequests,
    acceptedConnections,
    activeConversation,
    messageRequests,
    fetchContacts,
    inviteByUsername,
    acceptConnection,
    declineConnection,
    revokeConnection,
    blockUser,
    unblockUser,
    loadConversations,
    openThread,
    closeThread,
    sendMessage,
    acceptMessageRequest,
    declineMessageRequest,
  }
})
