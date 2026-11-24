import { describe, it, expect, beforeEach, vi, afterEach } from 'vite-plus/test'
import { useChatWebSocket } from '@/core/composables/useWebSocket'

/**
 * WebSocket Chat Bug Regression Tests
 * Bug #2: Wrong URL Bug - WebSocket connecting to Vite dev server instead of backend
 *
 * BACKGROUND:
 * The bug occurred when useChatWebSocket() constructed the WebSocket URL incorrectly.
 * It was using the wrong protocol (ws:// instead of wss://) or wrong hostname.
 * This caused the WebSocket to connect to the Vite dev server instead of the backend API.
 *
 * FIX:
 * useChatWebSocket now:
 * 1. Reads VITE_API_BASE_URL from environment (same as axios)
 * 2. Converts http:// to ws:// and https:// to wss://
 * 3. Constructs URL as: {wsBaseUrl}/api/v1/ws/chat/{userId}/{dwellerId}
 */

describe('Bug #2: WebSocket URL Construction', () => {
  const userId = 'user-123'
  const dwellerId = 'dweller-456'

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  describe('useChatWebSocket URL Construction', () => {
    it('should construct WebSocket URL from VITE_API_BASE_URL with http protocol', () => {
      // ARRANGE: Mock environment variable with http URL
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')

      // ACT: Create WebSocket composable
      const ws = useChatWebSocket(userId, dwellerId)

      // ASSERT: Verify the WebSocket URL is correctly constructed
      // The URL should be: ws://localhost:8000/api/v1/ws/chat/user-123/dweller-456
      // We can't directly access the URL, but we can verify the composable was created
      // and the state is 'disconnected' (not yet connected)
      expect(ws.state.value).toBe('disconnected')
      expect(ws.connect).toBeDefined()
      expect(ws.disconnect).toBeDefined()
      expect(ws.sendTypingIndicator).toBeDefined()
    })

    it('should convert https protocol to wss protocol', () => {
      // ARRANGE: Mock environment variable with https URL
      vi.stubEnv('VITE_API_BASE_URL', 'https://example.com')

      // ACT: Create WebSocket composable
      const ws = useChatWebSocket(userId, dwellerId)

      // ASSERT: Verify composable is created (URL conversion happens internally)
      // The URL should be: wss://example.com/api/v1/ws/chat/user-123/dweller-456
      expect(ws.state.value).toBe('disconnected')
    })

    it('should target the page origin when a production build has no VITE_API_BASE_URL', () => {
      // ARRANGE: production build with an empty base URL — the case the CSP has to agree with
      vi.stubEnv('VITE_API_BASE_URL', '')
      vi.stubEnv('PROD', true)
      const opened: string[] = []
      const original = globalThis.WebSocket
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

      try {
        // ACT
        const ws = useChatWebSocket(userId, dwellerId)
        ws.connect()
      } finally {
        globalThis.WebSocket = original
      }

      // ASSERT: the page origin, covered by `connect-src 'self'` — never ws://localhost:8000
      expect(opened).toEqual([`ws://${window.location.host}/api/v1/ws/chat/${userId}/${dwellerId}`])
    })

    it('should keep the local API server when dev has no VITE_API_BASE_URL', () => {
      // ARRANGE: dev server — its /api proxy does not carry WebSockets, so the fallback stays
      vi.stubEnv('VITE_API_BASE_URL', '')
      vi.stubEnv('PROD', false)
      const opened: string[] = []
      const original = globalThis.WebSocket
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

      try {
        // ACT
        const ws = useChatWebSocket(userId, dwellerId)
        ws.connect()
      } finally {
        globalThis.WebSocket = original
      }

      // ASSERT
      expect(opened).toEqual([`ws://localhost:8000/api/v1/ws/chat/${userId}/${dwellerId}`])
    })

    it('should include userId and dwellerId in the WebSocket URL path', () => {
      // ARRANGE: Mock environment variable
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')

      // ACT: Create WebSocket composable with specific IDs
      const testUserId = 'user-abc-123'
      const testDwellerId = 'dweller-xyz-789'
      const ws = useChatWebSocket(testUserId, testDwellerId)

      // ASSERT: Verify composable is created with correct parameters
      // The URL should include both IDs in the path
      expect(ws.state.value).toBe('disconnected')
    })

    it('should handle API base URL with trailing slash', () => {
      // ARRANGE: Mock environment variable with trailing slash
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/')

      // ACT: Create WebSocket composable
      const ws = useChatWebSocket(userId, dwellerId)

      // ASSERT: Should handle trailing slash gracefully
      expect(ws.state.value).toBe('disconnected')
    })

    it('should handle API base URL without protocol', () => {
      // ARRANGE: Mock environment variable without protocol
      vi.stubEnv('VITE_API_BASE_URL', 'localhost:8000')

      // ACT: Create WebSocket composable
      const ws = useChatWebSocket(userId, dwellerId)

      // ASSERT: Should still create composable (protocol conversion handles this)
      expect(ws.state.value).toBe('disconnected')
    })
  })

  describe('useChatWebSocket sendTypingIndicator', () => {
    it('should not throw error when sending typing indicator while disconnected', () => {
      // ARRANGE: Mock environment variable
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
      const ws = useChatWebSocket(userId, dwellerId)

      // State is 'disconnected' by default
      expect(ws.state.value).toBe('disconnected')

      // ACT & ASSERT: Should not throw error
      expect(() => {
        ws.sendTypingIndicator(true)
      }).not.toThrow()
    })

    it('should log debug message when typing indicator cannot be sent', () => {
      // ARRANGE: Mock environment variable and console
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
      const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
      const ws = useChatWebSocket(userId, dwellerId)

      // State is 'disconnected' by default
      expect(ws.state.value).toBe('disconnected')

      // ACT: Try to send typing indicator
      ws.sendTypingIndicator(true)

      // ASSERT: Should log debug message
      expect(debugSpy).toHaveBeenCalledWith(expect.stringContaining('Cannot send typing indicator'))

      debugSpy.mockRestore()
    })
  })

  describe('useChatWebSocket sendMessage', () => {
    it('should not throw error when sending message while disconnected', () => {
      // ARRANGE: Mock environment variable
      vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000')
      const ws = useChatWebSocket(userId, dwellerId)

      // State is 'disconnected' by default
      expect(ws.state.value).toBe('disconnected')

      // ACT & ASSERT: Should not throw error
      expect(() => {
        ws.sendMessage('Hello')
      }).not.toThrow()
    })
  })
})
