import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NotificationBell from '@/modules/vault/components/shell/NotificationBell.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { removePendingReport, usePendingReports } from '@/modules/exploration/composables/usePendingReports'

/**
 * NotificationBell SSE Watcher Regression Tests
 *
 * BACKGROUND:
 * A runtime error was observed in the browser during Playwright QA:
 * "Cannot read properties of null (reading 'value')" with a
 * "Unhandled error during execution of watcher getter" Vue warning, attributed
 * to NotificationBell.vue:63:31 — the watcher getter
 * `() => sse.value?.event.value ?? null`.
 *
 * INVESTIGATION RESULT:
 * The current code is null-safe:
 *  1. `sse.value` is `ref<ReturnType<typeof useSse>>()` — optional-chained, so
 *     an unset instance short-circuits to `undefined`.
 *  2. `useSse`/`useSseBase` always expose `event: ref<SseEvent | null>(null)` —
 *     a Ref object, never null — so `.value` on it can never throw.
 *  3. No git version of this file ever defined a `notificationData` function;
 *     the stack frame name could not be produced by this component.
 *
 * These tests lock in the null-safety of the watcher path end-to-end (real
 * `useSse` with a mocked fetch SSE stream), so a future refactor that removes
 * the optional chaining fails CI instead of crashing the browser.
 */

// Mock Iconify (no-op icon component)
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon" data-testid="mock-icon" />',
    props: ['icon'],
  },
}))

// Mock the axios plugin: NotificationBell only needs resolved API responses
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

import axios from '@/core/plugins/axios'

// Helper: create a mock fetch response with a controllable SSE stream
function createMockResponse(chunks: string[], options?: { hang?: boolean }) {
  const encoder = new TextEncoder()
  let index = 0
  let cancelled = false
  let pendingResolve: ((value: { done: boolean; value?: Uint8Array }) => void) | null = null

  const reader = {
    read: vi.fn().mockImplementation(() => {
      if (cancelled || (!options?.hang && index >= chunks.length)) {
        return Promise.resolve({ done: true, value: undefined })
      }
      if (index < chunks.length) {
        const chunk = chunks[index++]
        return Promise.resolve({ done: false, value: encoder.encode(chunk) })
      }
      // hang mode: return a promise that resolves when cancelled
      return new Promise<{ done: boolean; value?: Uint8Array }>((resolve) => {
        pendingResolve = resolve
      })
    }),
    cancel: vi.fn().mockImplementation(() => {
      cancelled = true
      if (pendingResolve) {
        pendingResolve({ done: true, value: undefined })
        pendingResolve = null
      }
      return Promise.resolve(undefined)
    }),
  }
  return {
    ok: true,
    body: {
      getReader: () => reader,
    },
  }
}

// Helper: encode SSE events into wire format chunks
function encodeSse(data: string, event?: string): string {
  let result = ''
  if (event) result += `event: ${event}\n`
  result += `data: ${data}\n\n`
  return result
}

const notifData = JSON.stringify({
  notification: {
    id: 'n1',
    notification_type: 'level_up',
    title: 'Level Up!',
    message: 'A dweller reached a new level',
    priority: 'normal',
    created_at: '2026-08-11T10:00:00',
    meta_data: {},
  },
})

describe('NotificationBell SSE watcher null-safety', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let errorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    window.localStorage.clear()
    setActivePinia(createPinia())

    // API mocks fall back to empty/valid responses
    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(axios.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
    ;(axios.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes('unread-count')) return Promise.resolve({ data: { count: 1 } })
      return Promise.resolve({ data: [] })
    })

    fetchMock = vi.fn()
    global.fetch = fetchMock

    // Any watcher getter error would surface here as a Vue warn
    errorSpy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
      console.log('CAPTURED_CONSOLE_ERROR:', JSON.stringify(args, (k, v) => (v instanceof Error ? v.message : v)))
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    errorSpy.mockRestore()
  })

  it('does not throw on the watcher getter when authenticated and an SSE notification arrives', async () => {
    // ARRANGE: authenticated user, SSE stream delivers a notification then hangs open
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse(notifData, 'notification')], { hang: true })
    )

    // ACT: mount (onMounted starts SSE) and let the stream flush
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: no watcher getter error was logged
    expect(errorSpy).not.toHaveBeenCalled()

    // ASSERT: the SSE event was processed — popup shows the notification
    await wrapper.find('button[title="Notifications"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Level Up!')
    expect(wrapper.text()).toContain('A dweller reached a new level')

    wrapper.unmount()
  })

  it('toasts and adds a bell entry when a hazard team join notification arrives', async () => {
    // ARRANGE: authenticated user, SSE delivers a hazard_team_joined notification
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    const { toasts } = useToast()
    toasts.value = []

    const hazardNotifData = JSON.stringify({
      notification: {
        id: 'n2',
        notification_type: 'hazard_team_joined',
        title: 'Hazard Team Joined',
        message: 'Jane Doe joined the fire team',
        priority: 'normal',
        created_at: '2026-08-11T10:00:00',
        meta_data: {
          dweller_id: 'd1',
          dweller_name: 'Jane Doe',
          team: 'fire',
          status: 'active',
          promoted: false,
          vault_id: 'vault-1',
        },
      },
    })
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse(hazardNotifData, 'notification')], { hang: true })
    )

    // ACT: mount (onMounted starts SSE) and let the stream flush
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: the event surfaced as a toast (progression red line)
    expect(toasts.value.some((t) => t.message === 'Jane Doe joined the fire team')).toBe(true)

    // ASSERT: the event also produced a normal bell entry
    await wrapper.find('button[title="Notifications"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Hazard Team Joined')
    expect(wrapper.text()).toContain('Jane Doe joined the fire team')

    wrapper.unmount()
  })

  it('surfaces an exploration completion that lands away from the exploration routes', async () => {
    // ARRANGE: authenticated user, SSE delivers the arrival notification
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    const { toasts } = useToast()
    toasts.value = []
    removePendingReport('exp-1')

    const completionData = JSON.stringify({
      notification: {
        id: 'n3',
        notification_type: 'exploration_complete',
        title: 'Exploration Complete',
        message: 'Lucy MacLean returned with 120 caps',
        priority: 'normal',
        created_at: '2026-08-11T11:00:00',
        vault_id: 'vault-1',
        meta_data: {
          exploration_id: 'exp-1',
          vault_id: 'vault-1',
          dweller_id: 'd1',
          dweller_name: 'Lucy MacLean',
          rewards: { caps: 120, items: [], experience: 40, distance: 3 },
        },
      },
    })
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse(completionData, 'notification')], { hang: true })
    )

    // ACT: mount (onMounted starts SSE) and let the stream flush
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: announced immediately, rather than only after a bell click
    expect(toasts.value.some((t) => t.message === 'Lucy MacLean returned with 120 caps')).toBe(true)

    // ASSERT: the reward report is queued without the player clicking the notification
    const { pendingReports } = usePendingReports('vault-1')
    expect(pendingReports.value.some((r) => r.explorationId === 'exp-1')).toBe(true)

    wrapper.unmount()
  })

  it('does not throw on the watcher getter when unauthenticated', async () => {
    // ARRANGE: no token — onMounted skips startSse, sse.value stays undefined
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))

    // ACT
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: no SSE connection attempted, no watcher error
    expect(fetchMock).not.toHaveBeenCalled()
    expect(errorSpy).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('handles a notification event with null payload data without throwing', async () => {
    // ARRANGE: authenticated, server sends a notification event whose data is null
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse('null', 'notification')], { hang: true })
    )

    // ACT
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: watcher ran `(evt.data as any)?.notification` on null — no throw
    expect(errorSpy).not.toHaveBeenCalled()

    // ASSERT: no notification was added (early return), popup shows empty state
    await wrapper.find('button[title="Notifications"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('No notifications yet')

    wrapper.unmount()
  })

  it('handles token change mid-lifecycle (login while mounted) without throwing', async () => {
    // ARRANGE: starts unauthenticated, then logs in (triggers the token watcher -> startSse)
    const authStore = useAuthStore()
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse(notifData, 'notification')], { hang: true })
    )

    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ACT: login while mounted
    authStore.token = 'test-token'
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    // ASSERT: SSE started, notification processed, no watcher error
    expect(fetchMock).toHaveBeenCalled()
    expect(errorSpy).not.toHaveBeenCalled()

    await wrapper.find('button[title="Notifications"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Level Up!')

    wrapper.unmount()
  })
})
