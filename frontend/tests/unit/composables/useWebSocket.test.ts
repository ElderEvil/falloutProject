import { describe, it, expect, beforeEach, vi, afterEach } from 'vite-plus/test'
import { useChatWebSocket } from '@/core/composables/useWebSocket'

/** Records the URL of every socket the composable opens, so URL construction is asserted. */
function recordSockets(): { opened: string[]; restore: () => void } {
  const original = globalThis.WebSocket
  const opened: string[] = []
  // @ts-expect-error - minimal stand-in for the browser WebSocket
  globalThis.WebSocket = class {
    static readonly CONNECTING = 0
    static readonly OPEN = 1
    onopen: null = null
    onmessage: null = null
    onclose: null = null
    onerror: null = null
    constructor(url: string) {
      opened.push(url)
    }
    send() {}
    close() {}
  }
  return { opened, restore: () => (globalThis.WebSocket = original) }
}

describe('useChatWebSocket', () => {
  const userId = 'user-123'
  const dwellerId = 'dweller-456'
  const path = `/api/v1/ws/chat/${userId}/${dwellerId}`

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it.each([
    ['http base', 'http://localhost:8000', `ws://localhost:8000${path}`],
    ['https base converted to wss', 'https://example.com', `wss://example.com${path}`],
    ['trailing slash stripped', 'http://localhost:8000/', `ws://localhost:8000${path}`],
    ['base without a protocol', 'localhost:8000', `ws://localhost:8000${path}`],
    ['dev fallback without a base', '', `ws://localhost:8000${path}`],
  ])('builds the socket URL from a %s', (_label, baseUrl, expected) => {
    vi.stubEnv('VITE_API_BASE_URL', baseUrl)
    vi.stubEnv('PROD', false)
    const sockets = recordSockets()

    try {
      useChatWebSocket(userId, dwellerId).connect()
    } finally {
      sockets.restore()
    }

    expect(sockets.opened).toEqual([expected])
  })

  it('targets the page origin when a production build has no VITE_API_BASE_URL', () => {
    // The CSP has to agree with this origin: `connect-src 'self'`, never ws://localhost:8000.
    vi.stubEnv('VITE_API_BASE_URL', '')
    vi.stubEnv('PROD', true)
    const sockets = recordSockets()

    try {
      useChatWebSocket(userId, dwellerId).connect()
    } finally {
      sockets.restore()
    }

    expect(sockets.opened).toEqual([`ws://${window.location.host}${path}`])
  })

  it('appends the token as a query parameter', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
    const sockets = recordSockets()

    try {
      useChatWebSocket(userId, dwellerId, 'auth token').connect()
    } finally {
      sockets.restore()
    }

    expect(sockets.opened).toEqual([`ws://localhost:8000${path}?token=auth%20token`])
  })

  it('starts disconnected and exposes its controls', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
    const ws = useChatWebSocket(userId, dwellerId)

    expect(ws.state.value).toBe('disconnected')
    expect(ws.connect).toBeDefined()
    expect(ws.disconnect).toBeDefined()
    expect(ws.sendTypingIndicator).toBeDefined()
  })

  describe('while disconnected', () => {
    beforeEach(() => {
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
    })

    it('should not throw when sending a typing indicator', () => {
      const ws = useChatWebSocket(userId, dwellerId)

      expect(ws.state.value).toBe('disconnected')
      expect(() => {
        ws.sendTypingIndicator(true)
      }).not.toThrow()
    })

    it('should log debug message when typing indicator cannot be sent', () => {
      const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
      const ws = useChatWebSocket(userId, dwellerId)

      expect(ws.state.value).toBe('disconnected')

      ws.sendTypingIndicator(true)

      expect(debugSpy).toHaveBeenCalledWith(expect.stringContaining('Cannot send typing indicator'))

      debugSpy.mockRestore()
    })

    it('should not throw when sending a message', () => {
      const ws = useChatWebSocket(userId, dwellerId)

      expect(ws.state.value).toBe('disconnected')
      expect(() => {
        ws.sendMessage('Hello')
      }).not.toThrow()
    })
  })
})
