import { ref, computed, watch, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useWebSocket as useVueUseWebSocket, tryOnUnmounted } from '@vueuse/core'

export type WebSocketState = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface WebSocketMessage {
  type: string
  [key: string]: unknown
}

export function useWebSocket(url?: MaybeRefOrGetter<string | URL | undefined>) {
  const handlers = new Map<string, ((m: WebSocketMessage) => void)[]>()

  const { status, data, send: rawSend, open, close, ws } = useVueUseWebSocket(url, {
    autoReconnect: {
      retries: 5,
      delay: (retry) => Math.min(1000 * 2 ** (retry - 1), 30000),
    },
    heartbeat: {
      message: 'ping',
      interval: 30000,
      pongTimeout: 5000,
    },
    immediate: false,
  })

  const state = computed<WebSocketState>(() =>
    status.value === 'CONNECTING'
      ? 'connecting'
      : status.value === 'OPEN'
        ? 'connected'
        : 'disconnected'
  )

  watch(data, (raw) => {
    if (!raw) return
    try {
      const msg: WebSocketMessage = typeof raw === 'string' ? JSON.parse(raw) : raw
      handlers.get(msg.type)?.forEach((h) => h(msg))
      handlers.get('*')?.forEach((h) => h(msg))
    } catch (e) {
      console.error('Error parsing WebSocket message:', e)
    }
  })

  const send = (message: WebSocketMessage) => {
    if (ws.value?.readyState === WebSocket.OPEN) {
      rawSend(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected, cannot send message')
    }
  }

  const on = <T extends WebSocketMessage = WebSocketMessage>(type: string, handler: (m: T) => void) => {
    if (!handlers.has(type)) handlers.set(type, [])
    handlers.get(type)!.push(handler as (m: WebSocketMessage) => void)
  }

  const off = <T extends WebSocketMessage = WebSocketMessage>(type: string, handler: (m: T) => void) => {
    const list = handlers.get(type)
    if (list) {
      const i = list.indexOf(handler as (m: WebSocketMessage) => void)
      if (i > -1) list.splice(i, 1)
    }
  }

  const connect = () => {
    open()
  }

  tryOnUnmounted(() => {
    handlers.clear()
    close()
  })

  return {
    state,
    lastError: ref<string | null>(null),
    reconnectAttempts: ref(0),
    connect,
    disconnect: close,
    send,
    on,
    off,
    close,
    ws,
    data,
    status: state,
  }
}

export function useChatWebSocket(userId: MaybeRefOrGetter<string>, dwellerId: MaybeRefOrGetter<string>) {
  const wsBase = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  const url = computed(() => `${wsBase}/api/v1/ws/chat/${toValue(userId)}/${toValue(dwellerId)}`)
  const ws = useWebSocket(url)

  const sendTypingIndicator = (isTyping: boolean) => {
    if (ws.state.value === 'connected') {
      ws.send({ type: 'typing', is_typing: isTyping })
    } else {
      console.debug(`Cannot send typing indicator: WebSocket is ${ws.state.value}, not connected`)
    }
  }

  const sendMessage = (content: string) => {
    if (ws.state.value === 'connected') {
      ws.send({ type: 'message', content })
    } else {
      console.debug(`Cannot send message: WebSocket is ${ws.state.value}, not connected`)
    }
  }

  const ping = () => {
    ws.send({ type: 'ping' })
  }

  return {
    ...ws,
    sendTypingIndicator,
    sendMessage,
    ping,
  }
}
