import { ref, watch, type Ref } from 'vue'
import { getErrorStatus } from '@/core/types/utils'
import {
  ensureAccessToken,
  expireSession,
  getStoredToken,
  refreshSession,
} from '@/core/utils/authSession'
import { useBackgroundActivity } from './useBackgroundActivity'

function safeJsonParse(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

/**
 * An SSE event parsed from the wire format.
 *
 * Per the SSE spec, `event` defaults to ``"message"`` when omitted,
 * `data` is the accumulated text (JSON-parsed if possible), and `id`
 * carries the last ``id:`` field value.
 */
export interface SseEvent {
  event: string
  data: unknown
  id: string | null
}

function parseSseLine(line: string): { field: string; value: string } | null {
  const colonIndex = line.indexOf(':')
  if (colonIndex === -1) return null
  const field = line.slice(0, colonIndex)
  let value = line.slice(colonIndex + 1)
  if (value.startsWith(' ')) value = value.slice(1)
  return { field, value }
}

async function readSseStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (evt: SseEvent) => void
): Promise<void> {
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  const currentData: string[] = []
  let currentId: string | null = null

  const dispatch = () => {
    const dataStr = currentData.join('\n')
    currentData.length = 0
    if (!dataStr && !currentEvent) return
    onEvent({
      event: currentEvent || 'message',
      data: dataStr ? safeJsonParse(dataStr) : '',
      id: currentId,
    })
    currentEvent = ''
    currentId = null
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line === '') {
        dispatch()
        continue
      }
      const parsed = parseSseLine(line)
      if (!parsed) continue
      switch (parsed.field) {
        case 'event':
          currentEvent = parsed.value
          break
        case 'data':
          currentData.push(parsed.value)
          break
        case 'id':
          currentId = parsed.value
          break
      }
    }
  }
  buffer += decoder.decode()
  const remaining = buffer.split('\n')
  for (const line of remaining) {
    if (line === '') {
      dispatch()
      continue
    }
    const parsed = parseSseLine(line)
    if (!parsed) continue
    switch (parsed.field) {
      case 'event':
        currentEvent = parsed.value
        break
      case 'data':
        currentData.push(parsed.value)
        break
      case 'id':
        currentId = parsed.value
        break
    }
  }
  if (currentData.length > 0 || currentEvent) dispatch()
}

// Shared SSE base — handles both GET and POST streaming
function useSseBase(
  url: string,
  options?: {
    method?: 'GET' | 'POST'
    headers?: Record<string, string> | (() => Record<string, string>)
  }
) {
  const backgroundStream = options?.method !== 'POST'
  let activity: ReturnType<typeof useBackgroundActivity> | null = null
  const canRun = () => activity?.canRun.value ?? true
  let requested = false
  let blocked = false
  let stopActivityWatch: (() => void) | null = null
  const event = ref<SseEvent | null>(null)
  const status = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')
  const error = ref<Error | null>(null)
  const reconnected = ref(0)
  let abortController: AbortController | null = null
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  let intentionalClose = false
  let attempt = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let lastBody: Record<string, unknown> | undefined = undefined

  const stopReconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const close = (isIntentional = true) => {
    if (isIntentional) {
      intentionalClose = true
      requested = false
      stopActivityWatch?.()
      stopActivityWatch = null
      activity?.stop()
      activity = null
    }
    stopReconnect()
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (reader) {
      reader.cancel().catch(() => {})
      reader = null
    }
    status.value = 'closed'
  }

  const scheduleReconnect = () => {
    // A submitted POST must never be replayed automatically.
    if (!backgroundStream || intentionalClose || blocked || reconnectTimer || !canRun()) return
    const delay = Math.min(1000 * 2 ** attempt, 30000)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      attempt++
      void connect(undefined, true)
    }, delay)
  }

  const connect = async (
    body?: Record<string, unknown>,
    fromReconnect = false,
    authRetried = false
  ): Promise<void> => {
    close(false)
    requested = true
    if (!fromReconnect && !authRetried) blocked = false
    if (backgroundStream && !stopActivityWatch) {
      activity = useBackgroundActivity(!!options?.headers)
      stopActivityWatch = watch(activity.canRun, (active) => {
        if (!active) close(false)
        else if (requested && !blocked) void connect(undefined, true)
      })
    }
    intentionalClose = false
    if (backgroundStream && !canRun()) return
    if (body !== undefined) lastBody = body
    if (fromReconnect) reconnected.value++
    status.value = 'connecting'
    error.value = null
    event.value = null
    const controller = new AbortController()
    abortController = controller

    try {
      if (options?.headers) await ensureAccessToken()
      if (abortController !== controller || controller.signal.aborted) return
      const isPost = (options?.method ?? 'GET') === 'POST'
      const rawHeaders = options?.headers
      const resolvedHeaders: Record<string, string> =
        typeof rawHeaders === 'function' ? rawHeaders() : (rawHeaders ?? {})
      const headers: Record<string, string> = { ...resolvedHeaders }
      const token = getStoredToken()
      if (headers.Authorization && token) headers.Authorization = `Bearer ${token}`
      if (isPost) headers['Content-Type'] = 'application/json'
      const response = await fetch(url, {
        method: options?.method ?? 'GET',
        headers,
        body: isPost ? JSON.stringify(lastBody ?? {}) : undefined,
        signal: abortController.signal,
      })
      if (abortController !== controller || controller.signal.aborted) return
      if (response.status === 401 && options?.headers && !authRetried) {
        if (!getStoredToken() || getStoredToken() === token) await refreshSession()
        if (abortController === controller && !controller.signal.aborted)
          return connect(undefined, false, true)
        return
      }
      if (!response.ok) {
        if (response.status === 401 && options?.headers) expireSession()
        throw Object.assign(new Error(`HTTP error! status: ${response.status}`), {
          status: response.status,
        })
      }
      if (!response.body) throw new Error('Response body is null')

      status.value = 'open'
      attempt = 0
      const activeReader = response.body.getReader()
      reader = activeReader
      await readSseStream(activeReader, (evt) => {
        if (abortController === controller) event.value = evt
      })
      if (abortController !== controller) return
      status.value = 'closed'
      scheduleReconnect()
    } catch (err) {
      if (abortController !== controller) return // stale invocation, ignore
      if (err instanceof DOMException && err.name === 'AbortError') {
        status.value = 'closed'
      } else {
        error.value = err instanceof Error ? err : new Error(String(err))
        status.value = 'closed'
      }
      const statusCode = getErrorStatus(err)
      if (statusCode && [401, 403, 404].includes(statusCode)) blocked = true
      scheduleReconnect()
    } finally {
      if (abortController === controller && intentionalClose) {
        reader = null
        abortController = null
      }
    }
  }

  return { event, status, error, reconnected, connect, close, stopReconnect }
}

// POST-based SSE composable (for chat etc.)

export interface UsePostEventStreamReturn {
  event: Ref<SseEvent | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed'>
  error: Ref<Error | null>
  reconnected: Ref<number>
  connect: (body: Record<string, unknown>) => Promise<void>
  close: () => void
  stopReconnect: () => void
}

export function usePostEventStream(
  url: string,
  options?: { headers?: Record<string, string> | (() => Record<string, string>) }
): UsePostEventStreamReturn {
  const { event, status, error, reconnected, connect, close, stopReconnect } = useSseBase(url, {
    ...options,
    method: 'POST',
  })
  return {
    event,
    status,
    error,
    reconnected,
    connect: connect as (body: Record<string, unknown>) => Promise<void>,
    close,
    stopReconnect,
  }
}

// Fetch-based GET SSE (supports Authorization headers for authenticated streams)

export interface UseSseReturn {
  event: Ref<SseEvent | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed'>
  error: Ref<Error | null>
  reconnected: Ref<number>
  start: () => Promise<void>
  close: () => void
  stopReconnect: () => void
}

export function useSse(
  url: string,
  options?: { headers?: Record<string, string> | (() => Record<string, string>) }
): UseSseReturn {
  const { event, status, error, reconnected, connect, close, stopReconnect } = useSseBase(url, {
    ...options,
    method: 'GET',
  })
  return { event, status, error, reconnected, start: connect, close, stopReconnect }
}
