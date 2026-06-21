import { ref, type Ref } from 'vue'
import { useEventSource, type UseEventSourceOptions } from '@vueuse/core'

export interface EventStreamOptions<Events extends string[] = string[]>
  extends Omit<UseEventSourceOptions<any>, 'autoReconnect'> {
  events?: Events
}

export interface UseEventStreamReturn<Events extends string[] = string[]> {
  data: Ref<any>
  event: Ref<Events[number] | null>
  status: Ref<'CONNECTING' | 'OPEN' | 'CLOSED'>
  error: Ref<Event | null>
  lastEventId: Ref<string | null>
  close: () => void
  open: () => void
}

function safeJsonParse(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

export function useEventStream<Events extends string[] = string[]>(
  url: string | Ref<string>,
  options?: EventStreamOptions<Events>
): UseEventStreamReturn<Events> {
  const events = options?.events

  const defaultOptions: UseEventSourceOptions<any> = {
    autoReconnect: {
      retries: 5,
      delay: 2000,
      onFailed() {
        console.error('SSE failed after 5 retries')
      },
    },
    serializer: {
      read: (raw?: string) => (raw ? safeJsonParse(raw) : null),
    },
  }

  const result = useEventSource(url, events, {
    ...defaultOptions,
    ...options,
    autoReconnect: options?.autoReconnect ?? defaultOptions.autoReconnect,
    serializer: options?.serializer ?? defaultOptions.serializer,
  })

  return {
    data: result.data,
    event: result.event,
    status: result.status,
    error: result.error,
    lastEventId: result.lastEventId,
    close: result.close,
    open: result.open,
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

// POST-based SSE composable (for chat etc.)

export interface UsePostEventStreamReturn {
  event: Ref<SseEvent | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed'>
  error: Ref<Error | null>
  connect: (body: Record<string, unknown>) => Promise<void>
  close: () => void
}

export function usePostEventStream(url: string): UsePostEventStreamReturn {
  const event = ref<SseEvent | null>(null)
  const status = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')
  const error = ref<Error | null>(null)
  let abortController: AbortController | null = null
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

  const close = () => {
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

  const connect = async (body: Record<string, unknown>) => {
    close()

    status.value = 'connecting'
    error.value = null
    event.value = null

    abortController = new AbortController()

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortController.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      status.value = 'open'
      reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      let currentEvent = ''
      const currentData: string[] = []
      let currentId: string | null = null

      const dispatch = () => {
        const dataStr = currentData.join('\n')
        currentData.length = 0

        // Empty line with no event type and no data = heartbeat / comment
        if (!dataStr && !currentEvent) return

        const parsed: unknown = dataStr ? safeJsonParse(dataStr) : ''
        event.value = { event: currentEvent || 'message', data: parsed, id: currentId }
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
            // 'retry' is deliberately not handled — reconnection logic
            // belongs in the consumer.
            default:
              break
          }
        }
      }

      // Flush any remaining data
      if (currentData.length > 0 || currentEvent) {
        dispatch()
      }

      status.value = 'closed'
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        status.value = 'closed'
      } else {
        error.value = err instanceof Error ? err : new Error(String(err))
        status.value = 'closed'
      }
    } finally {
      reader = null
      abortController = null
    }
  }

  return { event, status, error, connect, close }
}

// Fetch-based GET SSE (supports Authorization headers for authenticated streams)

export interface UseSseReturn {
  event: Ref<SseEvent | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed'>
  error: Ref<Error | null>
  start: () => Promise<void>
  close: () => void
}

export function useSse(url: string, options?: { headers?: Record<string, string> }): UseSseReturn {
  const event = ref<SseEvent | null>(null)
  const status = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')
  const error = ref<Error | null>(null)
  let abortController: AbortController | null = null
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

  const close = () => {
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

  const start = async () => {
    close()
    status.value = 'connecting'
    error.value = null
    event.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: options?.headers,
        signal: abortController.signal,
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      if (!response.body) throw new Error('Response body is null')

      status.value = 'open'
      reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''
      const currentData: string[] = []
      let currentId: string | null = null

      const dispatch = () => {
        const dataStr = currentData.join('\n')
        currentData.length = 0
        if (!dataStr && !currentEvent) return
        const parsed: unknown = dataStr ? safeJsonParse(dataStr) : ''
        event.value = { event: currentEvent || 'message', data: parsed, id: currentId }
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
          if (line === '') { dispatch(); continue }
          const parsed = parseSseLine(line)
          if (!parsed) continue
          switch (parsed.field) {
            case 'event': currentEvent = parsed.value; break
            case 'data': currentData.push(parsed.value); break
            case 'id': currentId = parsed.value; break
            default: break
          }
        }
      }
      if (currentData.length > 0 || currentEvent) dispatch()
      status.value = 'closed'
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        status.value = 'closed'
      } else {
        error.value = err instanceof Error ? err : new Error(String(err))
        status.value = 'closed'
      }
    } finally {
      reader = null
      abortController = null
    }
  }

  return { event, status, error, start, close }
}
