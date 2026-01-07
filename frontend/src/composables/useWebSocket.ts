import { ref, onUnmounted } from 'vue'

export type WebSocketState = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface WebSocketMessage {
  type: string
  [key: string]: any
}

export function useWebSocket(url: string) {
  const socket = ref<WebSocket | null>(null)
  const state = ref<WebSocketState>('disconnected')
  const lastError = ref<string | null>(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000

  const messageHandlers = new Map<string, ((message: WebSocketMessage) => void)[]>()

  const connect = () => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected')
      return
    }

    state.value = 'connecting'
    console.log('Connecting to WebSocket:', url)

    try {
      socket.value = new WebSocket(url)

      socket.value.onopen = () => {
        state.value = 'connected'
        reconnectAttempts.value = 0
        lastError.value = null
        console.log('WebSocket connected')
      }

      socket.value.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          console.log('WebSocket message received:', message)

          // Call registered handlers for this message type
          const handlers = messageHandlers.get(message.type)
          if (handlers) {
            handlers.forEach(handler => handler(message))
          }

          // Also call wildcard handlers
          const wildcardHandlers = messageHandlers.get('*')
          if (wildcardHandlers) {
            wildcardHandlers.forEach(handler => handler(message))
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      socket.value.onerror = (error) => {
        console.error('WebSocket error:', error)
        state.value = 'error'
        lastError.value = 'WebSocket connection error'
      }

      socket.value.onclose = () => {
        console.log('WebSocket disconnected')
        state.value = 'disconnected'
        socket.value = null

        // Attempt to reconnect
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          console.log(`Reconnecting in ${reconnectDelay}ms... (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`)
          setTimeout(() => {
            connect()
          }, reconnectDelay)
        } else {
          console.error('Max reconnection attempts reached')
          lastError.value = 'Failed to reconnect after multiple attempts'
        }
      }
    } catch (error) {
      console.error('Error creating WebSocket:', error)
      state.value = 'error'
      lastError.value = 'Failed to create WebSocket connection'
    }
  }

  const disconnect = () => {
    if (socket.value) {
      reconnectAttempts.value = maxReconnectAttempts // Prevent auto-reconnect
      socket.value.close()
      socket.value = null
    }
    state.value = 'disconnected'
  }

  const send = (message: WebSocketMessage) => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message))
      console.log('WebSocket message sent:', message)
    } else {
      console.error('WebSocket not connected, cannot send message')
      throw new Error('WebSocket not connected')
    }
  }

  const on = (messageType: string, handler: (message: WebSocketMessage) => void) => {
    if (!messageHandlers.has(messageType)) {
      messageHandlers.set(messageType, [])
    }
    messageHandlers.get(messageType)!.push(handler)
  }

  const off = (messageType: string, handler: (message: WebSocketMessage) => void) => {
    const handlers = messageHandlers.get(messageType)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
    messageHandlers.clear()
  })

  return {
    // State
    state,
    lastError,
    reconnectAttempts,

    // Methods
    connect,
    disconnect,
    send,
    on,
    off
  }
}

// Specific composable for chat WebSocket
export function useChatWebSocket(userId: string, dwellerId: string) {
  const wsUrl = `ws://localhost:8000/api/v1/ws/chat/${userId}/${dwellerId}`
  const ws = useWebSocket(wsUrl)

  const sendTypingIndicator = (isTyping: boolean) => {
    ws.send({
      type: 'typing',
      is_typing: isTyping
    })
  }

  const sendMessage = (content: string) => {
    ws.send({
      type: 'message',
      content
    })
  }

  const ping = () => {
    ws.send({ type: 'ping' })
  }

  return {
    ...ws,
    sendTypingIndicator,
    sendMessage,
    ping
  }
}
