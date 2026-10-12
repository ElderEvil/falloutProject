import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import { handleStoreError } from '@/core/utils/errorHandler'
import { messagesService } from '../services/messagesService'
import type { ConnectionRead, UserBlockRead } from '../models/messages'

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
  const isLoading = ref(false)
  const isInviting = ref(false)
  const busyUserId = ref<string | null>(null)
  const loadError = ref<string | null>(null)

  const enabled = computed(() => featureFlags.playerConnections)
  const me = computed(() => authStore.user?.id ?? null)
  const incomingRequests = computed(() =>
    connections.value.filter((c) => c.status === 'pending' && c.addressee_id === me.value)
  )
  const outgoingRequests = computed(() =>
    connections.value.filter((c) => c.status === 'pending' && c.requester_id === me.value)
  )
  const acceptedConnections = computed(() => connections.value.filter((c) => c.status === 'accepted'))

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
      handleStoreError(error, 'Failed to unblock user')
    } finally {
      busyUserId.value = null
    }
  }

  return {
    connections,
    blocks,
    isLoading,
    isInviting,
    busyUserId,
    loadError,
    enabled,
    me,
    counterpartId,
    incomingRequests,
    outgoingRequests,
    acceptedConnections,
    fetchContacts,
    inviteByUsername,
    acceptConnection,
    declineConnection,
    revokeConnection,
    blockUser,
    unblockUser,
  }
})