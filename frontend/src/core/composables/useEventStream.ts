import { ref } from 'vue'

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
  onEvent: (evt: SseEvent) => void,
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
      if (line === '') { dispatch(); continue }
      const parsed = parseSseLine(line)
      if (!parsed) continue
      switch (parsed.field) {
        case 'event': currentEvent = parsed.value; break
        case 'data': currentData.push(parsed.value); break
        case 'id': currentId = parsed.value; break
      }
    }
  }
  buffer += decoder.decode()
  const remaining = buffer.split('\n')
  for (const line of remaining) {
    if (line === '') { dispatch(); continue }
    const parsed = parseSseLine(line)
    if (!parsed) continue
    switch (parsed.field) {
      case 'event': currentEvent = parsed.value; break
      case 'data': currentData.push(parsed.value); break
      case 'id': currentId = parsed.value; break
    }
  }
  if (currentData.length > 0 || currentEvent) dispatch()
}

// POST-based SSE composable (for chat etc.)

export interface UsePostEventStreamReturn {
  event: Ref<SseEvent | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed'>
  error: Ref<Error | null>
  connect: (body: Record<string, unknown>) => Promise<void>
  close: () => void
}

export function usePostEventStream(url: string, options?: { headers?: Record<string, string> }): UsePostEventStreamReturn {
  const event = ref<SseEvent | null>(null)
  const status = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')
  const error = ref<Error | null>(null)
  let abortController: AbortController | null = null
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

  const close = () => {
    if (abortController) { abortController.abort(); abortController = null }
    if (reader) { reader.cancel().catch(() => {}); reader = null }
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
        headers: { 'Content-Type': 'application/json', ...options?.headers },
        body: JSON.stringify(body),
        signal: abortController.signal,
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      if (!response.body) throw new Error('Response body is null')

      status.value = 'open'
      reader = response.body.getReader()
      await readSseStream(reader, (evt) => { event.value = evt })
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
    if (abortController) { abortController.abort(); abortController = null }
    if (reader) { reader.cancel().catch(() => {}); reader = null }
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
      await readSseStream(reader, (evt) => { event.value = evt })
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
