import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createAxiosMock, createIconifyMock, createRouterMock } from '../../helpers/mocks'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NotificationBell from '@/modules/vault/components/shell/NotificationBell.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useNotificationInboxStore } from '@/modules/vault/stores/notificationInbox'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { audioManager } from '@/core/audio/audioManager'
import { isTauri } from '@tauri-apps/api/core'
import { sendNotification } from '@tauri-apps/plugin-notification'
import {
  removePendingReport,
  usePendingReports,
} from '@/modules/exploration/composables/usePendingReports'

/**
 * NotificationBell streams notifications over SSE. These tests drive the real
 * `useSse` with a mocked fetch stream, so the watcher path
 * (`() => sse.value?.event.value ?? null`) is exercised end-to-end: a refactor
 * that drops the optional chaining crashes here instead of in the browser.
 */
vi.mock('@iconify/vue', () =>
  createIconifyMock({
    template: '<span class="icon-mock" :data-icon="icon" data-testid="mock-icon" />',
  })
)
vi.mock('@/core/plugins/axios', () => createAxiosMock())
vi.mock('@tauri-apps/api/core', () => ({ isTauri: vi.fn(() => false) }))
vi.mock('@tauri-apps/api/path', () => ({
  resolveResource: vi.fn(async () => '/resources/notification-icon.png'),
}))
vi.mock('@tauri-apps/plugin-notification', () => ({
  isPermissionGranted: vi.fn(async () => true),
  sendNotification: vi.fn(),
}))
const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))
vi.mock('vue-router', () => createRouterMock({ push: mockPush }))

import axios from '@/core/plugins/axios'

/** A fetch response whose body streams `chunks` as SSE; `hang` keeps it open. */
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
        return Promise.resolve({ done: false, value: encoder.encode(chunks[index++]) })
      }
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
  return { ok: true, body: { getReader: () => reader } }
}

function encodeSse(data: string, event?: string): string {
  return `${event ? `event: ${event}\n` : ''}data: ${data}\n\n`
}

const baseNotification = {
  id: 'n1',
  notification_type: 'level_up',
  title: 'Level Up!',
  message: 'A dweller reached a new level',
  priority: 'normal',
  created_at: '2026-08-11T10:00:00',
  meta_data: {},
}

const notification = (overrides: Record<string, unknown> = {}) => ({
  ...baseNotification,
  ...overrides,
})

const actionableNotification = notification({
  id: 'act-1',
  vault_id: 'vault-1',
  title: 'Actionable Alert',
  message: 'Open the dweller list',
  is_read: false,
  created_at: '2026-08-11T10:00:00',
})

const informationalNotification = notification({
  id: 'info-1',
  vault_id: null,
  notification_type: 'resource_low',
  title: 'Informational Note',
  message: 'Power reserves are low',
  priority: 'info',
  is_read: false,
  created_at: '2026-08-11T09:00:00',
})

let fetchMock: ReturnType<typeof vi.fn>
const signedIn = (token = 'test-token') => {
  useAuthStore().token = token
}
const toastsWith = (message: string) =>
  useToast().toasts.value.filter((toast) => toast.message === message)
const openBell = async (wrapper: VueWrapper) => {
  await wrapper.get('button[aria-haspopup="dialog"]').trigger('click')
  await flushPromises()
}
const markAllRead = async (wrapper: VueWrapper) => {
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Mark all read')!
    .trigger('click')
  await flushPromises()
}
const bellBadge = (wrapper: VueWrapper) => wrapper.get('button[aria-haspopup="dialog"]').text()

const streamNotification = (payload: Record<string, unknown>, times = 1) =>
  fetchMock.mockResolvedValue(
    createMockResponse(
      Array(times).fill(encodeSse(JSON.stringify({ notification: payload }), 'notification')),
      {
        hang: true,
      }
    )
  )

const rushNotification = (id: string) =>
  notification({
    id,
    vault_id: 'vault-1',
    notification_type: 'rush_succeeded',
    title: 'Rush succeeded',
    message: 'Rush succeeded',
    created_at: '2026-11-01T10:00:00',
  })

/** Feed one notification through the SSE stream and let the watcher run. */
const deliver = async (
  payload: Record<string, unknown>,
  { times = 1, hang = true }: { times?: number; hang?: boolean } = {}
) => {
  const chunk = encodeSse(JSON.stringify({ notification: payload }), 'notification')
  fetchMock.mockResolvedValue(createMockResponse(Array(times).fill(chunk), { hang }))
  const wrapper = mount(NotificationBell)
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  return wrapper
}

const mockNotificationList = (items: Array<Record<string, unknown>>) => {
  ;(axios.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    if (url.includes('unread-count')) {
      return Promise.resolve({ data: { count: items.filter((item) => !item.is_read).length } })
    }
    return Promise.resolve({ data: items.map((item) => ({ ...item })) })
  })
}

const mountBell = async (items: Array<Record<string, unknown>> = []) => {
  signedIn()
  fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))
  mockNotificationList(items)
  const wrapper = mount(NotificationBell, { attachTo: document.body })
  await vi.advanceTimersByTimeAsync(0)
  await flushPromises()
  return wrapper
}

const mountAndOpen = async (items: Array<Record<string, unknown>>) => {
  const wrapper = await mountBell(items)
  await openBell(wrapper)
  return wrapper
}

// Transition removal runs on requestAnimationFrame; step the fake clock so the
// popup has left the DOM before a close is asserted.
const settleClose = async () => {
  await vi.advanceTimersByTimeAsync(100)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  window.localStorage.clear()
  setActivePinia(createPinia())
  useVaultBoyFeedback().clear()
  vi.mocked(isTauri).mockReturnValue(false)
  vi.mocked(sendNotification).mockClear()
  ;(axios.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) =>
    Promise.resolve({ data: String(url).includes('unread-count') ? { count: 1 } : [] })
  )
  ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
  ;(axios.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
  fetchMock = vi.fn()
  global.fetch = fetchMock
  mockPush.mockClear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('NotificationBell SSE watcher null-safety', () => {
  let errorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Any watcher getter error surfaces here as a Vue warn.
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it.each(['vault-1', 'other-vault'])(
    'deduplicates native hidden-window alerts and restricts them to the active vault (%s)',
    async (vaultId) => {
      vi.mocked(isTauri).mockReturnValue(true)
      vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
      signedIn()
      useVaultStore().activeVaultId = 'vault-1'
      const payload = notification({ vault_id: vaultId })

      const wrapper = await deliver(payload, { times: 2 })

      expect(sendNotification).toHaveBeenCalledTimes(vaultId === 'vault-1' ? 1 : 0)
      if (vaultId === 'vault-1')
        expect(sendNotification).toHaveBeenCalledWith({
          title: payload.title,
          body: payload.message,
          icon: '/resources/notification-icon.png',
        })
      wrapper.unmount()
    }
  )

  it.each(['vault-1', 'other-vault'])(
    'uses the persisted vault selection for a hidden-window alert before hydration (%s)',
    async (vaultId) => {
      vi.mocked(isTauri).mockReturnValue(true)
      vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
      signedIn()
      const vault = useVaultStore()
      vault.activeVaultId = null
      vault.selectedVaultId = 'vault-1'

      const wrapper = await deliver(notification({ vault_id: vaultId }))

      expect(sendNotification).toHaveBeenCalledTimes(vaultId === 'vault-1' ? 1 : 0)
      wrapper.unmount()
    }
  )

  it.each(['vault-1', 'other-vault'])(
    'animates a birth only for the active vault (%s)',
    async (id) => {
      signedIn()
      useVaultStore().activeVaultId = 'vault-1'
      const message = 'A baby was born!'

      const wrapper = await deliver(
        notification({ notification_type: 'baby_born', vault_id: id, message })
      )

      if (id === 'vault-1')
        expect(useVaultBoyFeedback().current.value).toMatchObject({
          animation: 'baby',
          vaultId: id,
        })
      else expect(useVaultBoyFeedback().current.value).toBeNull()
      expect(toastsWith(message)).toHaveLength(1)
      wrapper.unmount()
    }
  )

  it('surfaces a training completion missed while the stream was paused', async () => {
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    signedIn()
    fetchMock.mockImplementation(() => Promise.resolve(createMockResponse([], { hang: true })))
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    useToast().toasts.value = []
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)

    const completed = notification({
      notification_type: 'training_complete',
      message: 'Training finished while away',
      is_read: false,
    })
    vi.mocked(axios.get).mockImplementation(async (url) => ({
      data: String(url).includes('unread-count') ? { count: 1 } : [completed],
    }))
    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    const matching = toastsWith('Training finished while away')
    expect(matching).toHaveLength(1)
    expect(matching[0].count).toBe(1)
    wrapper.unmount()
  })

  it('toasts a site discovery once when the transport delivers it twice', async () => {
    signedIn()
    const payload = notification({
      notification_type: 'exploration_update',
      message: 'Lucy found Red Rocket. Enter before arriving home.',
      meta_data: { event: 'site_found', exploration_id: 'exp-1', site_id: 'red_rocket' },
    })

    const wrapper = await deliver(payload, { times: 2 })

    const reports = useToast().toasts.value.filter((toast) =>
      toast.message.includes('found Red Rocket')
    )
    expect(reports).toHaveLength(1)
    expect(reports[0].count).toBe(1)
    wrapper.unmount()
  })

  it.each([
    ['objective_completed', 'objectiveReady'],
    ['level_up', 'levelUp'],
    ['training_complete', 'trainingComplete'],
    ['radio_new_dweller', 'radioRecruit'],
    ['resource_low', 'resourceLow'],
  ])('plays one %s cue when a notification is delivered twice', async (type, sound) => {
    const play = vi.spyOn(audioManager, 'play').mockImplementation(() => {})
    signedIn()

    const wrapper = await deliver(notification({ notification_type: type }), { times: 2 })

    expect(play).toHaveBeenCalledExactlyOnceWith(sound, 'ui')
    await openBell(wrapper)
    expect(wrapper.findAll('[data-notification-id="n1"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('does not throw on the watcher getter when authenticated and an SSE notification arrives', async () => {
    signedIn()
    fetchMock.mockResolvedValue(
      createMockResponse(
        [encodeSse(JSON.stringify({ notification: baseNotification }), 'notification')],
        {
          hang: true,
        }
      )
    )

    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    expect(errorSpy).not.toHaveBeenCalled()
    await openBell(wrapper)
    expect(wrapper.text()).toContain('Level Up!')
    expect(wrapper.text()).toContain('A dweller reached a new level')
    wrapper.unmount()
  })

  it.each([
    { event: 'child_adopted', toastCount: 1 },
    { event: 'partner', toastCount: 0 },
  ])(
    'announces adoption without toasting other relationship events ($event)',
    async ({ event, toastCount }) => {
      signedIn()
      useToast().toasts.value = []
      const payload = notification({
        id: 'adopted-child',
        notification_type: 'relationship_formed',
        meta_data: { event },
        message: 'Alice and Bob adopted Lucy.',
        from_dweller_id: 'child-1',
        vault_id: 'vault-1',
      })

      const wrapper = await deliver(payload, { times: 2 })

      const matching = toastsWith(payload.message)
      expect(matching).toHaveLength(toastCount)
      if (toastCount) expect(matching[0].count).toBe(1)
      await openBell(wrapper)
      expect(wrapper.text()).toContain(payload.message)
      wrapper.unmount()
    }
  )

  it.each(['Training continues', 'Goal reached', 'Training complete'])(
    'shows the %s outcome in both toast and bell',
    async (outcome) => {
      signedIn()
      useToast().toasts.value = []
      const message = `Strength +1 (6). ${outcome}.`

      const wrapper = await deliver({
        id: 'training-notification',
        vault_id: 'vault-1',
        notification_type: 'training_complete',
        title: `Lucy — ${outcome}`,
        message,
        priority: 'normal',
        created_at: '2026-10-21T12:00:00',
        meta_data: {},
      })

      expect(toastsWith(message)).toHaveLength(1)
      await openBell(wrapper)
      expect(wrapper.text()).toContain(message)
      wrapper.unmount()
    }
  )

  it.each([
    {
      type: 'hazard_team_joined',
      title: 'Hazard Team Joined',
      message: 'Jane Doe joined the fire team',
      meta: { dweller_id: 'd1', dweller_name: 'Jane Doe', team: 'fire', status: 'active' },
    },
    {
      type: 'arena_morale_boost',
      title: 'Arena morale boost',
      message: 'Arena show lifted vault morale',
      meta: { room_id: 'arena-1' },
    },
    {
      type: 'quest_complete',
      title: 'Quest Party Returned',
      message: "'A Pier into the Future' party has returned! Rewards are ready to claim.",
      meta: { quest_id: 'quest-1', quest_title: 'A Pier into the Future', ready_to_claim: true },
      icon: 'mdi:treasure-chest',
    },
    {
      type: 'location_cleared',
      title: 'Megaton cleared',
      message: 'Megaton has been cleared. It will be ready to loot again soon.',
      icon: 'mdi:flag-checkered',
    },
    {
      type: 'location_ready',
      title: 'Megaton ready',
      message: 'Megaton is ready to be cleared again.',
      icon: 'mdi:map-marker-refresh',
    },
    {
      type: 'objective_completed',
      title: 'Objective Complete',
      message: 'Objective complete: Scrap 1 Baseball bat',
    },
    {
      type: 'objectives_refreshed',
      title: 'Objective Complete',
      message: 'Objective complete: Scrap 1 Baseball bat',
    },
    {
      type: 'storage_item_degraded',
      title: 'Storage maintenance',
      message: 'A stored weapon changed catalog variant',
      icon: 'mdi:tools',
    },
    {
      type: 'storage_item_upgraded',
      title: 'Storage maintenance',
      message: 'A stored weapon changed catalog variant',
      icon: 'mdi:arrow-up-bold',
    },
  ])('announces $type in the toast and the bell', async ({ type, title, message, meta, icon }) => {
    signedIn()
    useToast().toasts.value = []

    const wrapper = await deliver(
      notification({ notification_type: type, title, message, meta_data: meta ?? {} })
    )

    expect(toastsWith(message)).toHaveLength(1)
    await openBell(wrapper)
    expect(wrapper.text()).toContain(title)
    expect(wrapper.text()).toContain(message)
    if (icon) expect(wrapper.find(`[data-icon="${icon}"]`).exists()).toBe(true)
    wrapper.unmount()
  })

  it('surfaces an exploration completion that lands away from the exploration routes', async () => {
    signedIn()
    useToast().toasts.value = []
    removePendingReport('exp-1')
    const message = 'Lucy MacLean returned with 120 caps'

    const wrapper = await deliver({
      id: 'n3',
      notification_type: 'exploration_complete',
      title: 'Exploration Complete',
      message,
      vault_id: 'vault-1',
      meta_data: {
        exploration_id: 'exp-1',
        dweller_id: 'd1',
        dweller_name: 'Lucy MacLean',
        rewards: { caps: 120, items: [], experience: 40, distance: 3 },
      },
    })

    expect(toastsWith(message)).toHaveLength(1)
    const { pendingReports } = usePendingReports('vault-1')
    expect(pendingReports.value.some((report) => report.explorationId === 'exp-1')).toBe(true)
    wrapper.unmount()
  })

  it('does not toast a quest_complete notification that is not ready to claim', async () => {
    signedIn()
    useToast().toasts.value = []

    const wrapper = await deliver({
      id: 'n5',
      notification_type: 'quest_complete',
      title: 'Quest Party Returned',
      message: "'A Pier into the Future' party has returned! Rewards are ready to claim.",
      priority: 'high',
      created_at: '2026-08-11T12:00:00',
      vault_id: 'vault-1',
      meta_data: {
        quest_id: 'quest-1',
        quest_title: 'A Pier into the Future',
        phase: 'returned',
        ready_to_claim: false,
        vault_id: 'vault-1',
      },
    })

    expect(
      useToast().toasts.value.some((toast) => toast.message.includes('party has returned'))
    ).toBe(false)
    await openBell(wrapper)
    expect(wrapper.text()).toContain('Quest Party Returned')
    wrapper.unmount()
  })

  it('does not throw on the watcher getter when unauthenticated', async () => {
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))

    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(errorSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handles a notification event with null payload data without throwing', async () => {
    signedIn()
    fetchMock.mockResolvedValue(
      createMockResponse([encodeSse('null', 'notification')], { hang: true })
    )

    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    expect(errorSpy).not.toHaveBeenCalled()
    await openBell(wrapper)
    expect(wrapper.text()).toContain('No notifications yet')
    wrapper.unmount()
  })

  it('handles token change mid-lifecycle (login while mounted) without throwing', async () => {
    fetchMock.mockResolvedValue(
      createMockResponse(
        [encodeSse(JSON.stringify({ notification: baseNotification }), 'notification')],
        {
          hang: true,
        }
      )
    )

    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    signedIn()
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalled()
    expect(errorSpy).not.toHaveBeenCalled()
    await openBell(wrapper)
    expect(wrapper.text()).toContain('Level Up!')
    wrapper.unmount()
  })
})

describe('NotificationBell popup accessibility', () => {
  it('constrains the popup to the viewport and wires the bell/popup ARIA', async () => {
    const wrapper = await mountBell([informationalNotification])
    const bell = wrapper.get('button[aria-haspopup="dialog"]')

    expect(bell.attributes('aria-expanded')).toBe('false')
    expect(bell.attributes('aria-controls')).toBe('notifications-popup')
    await openBell(wrapper)

    const popup = wrapper.get('[role="dialog"]')
    expect(popup.attributes('id')).toBe('notifications-popup')
    expect(popup.attributes('aria-label')).toBe('Notifications')
    // jsdom has no CSS pipeline, so the viewport clamp is asserted on the class attr.
    expect(popup.attributes('class')).toMatch(/w-\[min\(24rem,calc\(100vw_-_1rem\)\)\]/)
    expect(popup.attributes('class')).not.toMatch(/(^|\s)w-96(\s|$)/)
    expect(wrapper.get('.notification-backdrop').attributes('aria-hidden')).toBe('true')
    expect(bell.attributes('aria-expanded')).toBe('true')

    await bell.trigger('click')
    await settleClose()
    expect(bell.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each(['Escape', 'backdrop'] as const)(
    'closes on %s and returns focus to the bell',
    async (how) => {
      const wrapper = await mountAndOpen([informationalNotification])
      expect(document.activeElement).toBe(wrapper.get('[role="dialog"]').element)

      if (how === 'Escape') window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      else await wrapper.get('.notification-backdrop').trigger('click')
      await settleClose()

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
      expect(document.activeElement).toBe(wrapper.get('button[aria-haspopup="dialog"]').element)
      wrapper.unmount()
    }
  )

  it('refreshes its unread count when a message is marked read in the full inbox', async () => {
    const items = [{ ...informationalNotification }]
    const wrapper = await mountBell(items)
    vi.mocked(axios.patch).mockImplementation(() => {
      items[0]!.is_read = true
      return Promise.resolve({ data: {} })
    })

    await useNotificationInboxStore().markRead('info-1')
    await flushPromises()

    expect(wrapper.findAll('span').some((span) => span.text() === '1')).toBe(false)
    await openBell(wrapper)
    expect(wrapper.get('[data-notification-id="info-1"]').text()).not.toContain('New')
    wrapper.unmount()
  })

  it('loads the twenty most recent notifications across all vaults', async () => {
    useVaultStore().activeVaultId = 'vault-1'
    const wrapper = await mountBell([informationalNotification])

    expect(axios.get).toHaveBeenCalledWith(
      '/api/v1/notifications/',
      expect.objectContaining({ params: expect.objectContaining({ limit: 20 }) })
    )
    const listCall = vi
      .mocked(axios.get)
      .mock.calls.find(([url]) => url === '/api/v1/notifications/')
    expect(listCall?.[1]?.params?.vault_id).toBeUndefined()
    wrapper.unmount()
  })

  it('renders rows owned by the inbox store without fetching a second list', async () => {
    signedIn()
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))
    vi.mocked(axios.get).mockImplementation((url) =>
      String(url).includes('unread-count')
        ? Promise.resolve({ data: { count: 1 } })
        : Promise.resolve({ data: [] })
    )
    useNotificationInboxStore().receiveNotification({
      ...notification({
        id: 'store-owned',
        vault_id: 'vault-1',
        from_dweller_id: null,
        title: 'Store owned',
        message: 'The inbox store owns this row',
        is_read: false,
        is_dismissed: false,
        user_id: 'user-1',
        read_at: null,
      }),
    })
    const wrapper = mount(NotificationBell)
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    const listRequests = () =>
      vi.mocked(axios.get).mock.calls.filter(([url]) => url === '/api/v1/notifications/')
    const before = listRequests().length

    await openBell(wrapper)

    expect(listRequests()).toHaveLength(before)
    expect(wrapper.get('[data-notification-id="store-owned"]').text()).toContain('Store owned')
    wrapper.unmount()
  })

  it('marks notifications across all vaults read from the bell and clears the badge', async () => {
    useVaultStore().activeVaultId = 'vault-1'
    const items = [{ ...actionableNotification }, { ...informationalNotification }]
    const wrapper = await mountAndOpen(items)
    vi.mocked(axios.post).mockImplementation((url) => {
      if (url === '/api/v1/notifications/mark-all-read') {
        items.forEach((item) => {
          item.is_read = true
        })
      }
      return Promise.resolve({ data: {} })
    })

    await markAllRead(wrapper)

    expect(axios.post).toHaveBeenCalledOnce()
    const [url, body, config] = vi.mocked(axios.post).mock.calls[0]
    expect(url).toBe('/api/v1/notifications/mark-all-read')
    expect(body).toEqual({})
    expect(config?.params?.vault_id).toBeUndefined()
    expect(wrapper.get('[data-notification-id="act-1"]').text()).not.toContain('New')
    expect(wrapper.get('[data-notification-id="info-1"]').text()).not.toContain('New')
    expect(bellBadge(wrapper)).toBe('')
    wrapper.unmount()
  })

  it('guards the unread count across session changes', async () => {
    const auth = useAuthStore()
    auth.token = 'previous-session'
    auth.user = { id: 'same-account' } as NonNullable<typeof auth.user>
    fetchMock.mockImplementation(async () => createMockResponse([], { hang: true }))
    let finish!: (value: { data: { count: number } }) => void
    let counts = 0
    vi.mocked(axios.get).mockImplementation((url) => {
      if (!String(url).includes('unread-count')) return Promise.resolve({ data: [] })
      if (counts++ > 0) return Promise.resolve({ data: { count: 5 } })
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    const wrapper = mount(NotificationBell)
    await flushPromises()

    // A logout discards the in-flight count...
    auth.token = null
    await flushPromises()
    finish({ data: { count: 9 } })
    await flushPromises()
    expect(bellBadge(wrapper)).toBe('')

    auth.token = 'refreshed-token'
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()
    expect(auth.user?.id).toBe('same-account')
    expect(bellBadge(wrapper)).toBe('5')
    wrapper.unmount()
  })

  it.each([false, true])(
    'scopes pending mark-all results to the same account (%s)',
    async (sameAccount) => {
      const wrapper = await mountAndOpen([{ ...informationalNotification }])
      const auth = useAuthStore()
      auth.user = { id: 'initial-account' } as NonNullable<typeof auth.user>
      let finish!: (value: { data: object }) => void
      vi.mocked(axios.post).mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        })
      )

      await markAllRead(wrapper)
      expect(axios.post).toHaveBeenCalledOnce()

      const nextNotification = notification({
        ...informationalNotification,
        id: 'next-account-notification',
        title: 'Next account alert',
      })
      mockNotificationList([nextNotification])
      fetchMock.mockImplementation(async () =>
        createMockResponse(
          [encodeSse(JSON.stringify({ notification: nextNotification }), 'notification')],
          {
            hang: true,
          }
        )
      )
      auth.user = { id: sameAccount ? 'initial-account' : 'next-account' } as NonNullable<
        typeof auth.user
      >
      auth.token = 'next-account-token'
      await vi.advanceTimersByTimeAsync(0)
      await flushPromises()
      expect(wrapper.get('[data-notification-id="next-account-notification"]').text()).toContain(
        'New'
      )
      expect(bellBadge(wrapper)).toBe('1')

      if (sameAccount) mockNotificationList([{ ...nextNotification, is_read: true }])
      finish({ data: {} })
      await flushPromises()

      expect(
        wrapper.get('[data-notification-id="next-account-notification"]').text().includes('New')
      ).toBe(!sameAccount)
      expect(bellBadge(wrapper)).toBe(sameAccount ? '' : '1')
      wrapper.unmount()
    }
  )

  it.each(['single', 'all'])(
    'updates retained bell rows after a %s read with separate server objects',
    async (action) => {
      const server = Array.from({ length: 20 }, (_, i) => ({
        ...actionableNotification,
        id: `older-${i + 1}`,
        title: `Older ${i + 1}`,
      }))
      const newest = { ...actionableNotification, id: 'newest', title: 'Newest' }
      signedIn('signed-in')
      vi.mocked(axios.get).mockImplementation(async (url) => ({
        data: String(url).includes('unread-count')
          ? { count: server.filter((item) => !item.is_read).length }
          : server.slice(0, 20).map((item) => ({ ...item })),
      }))
      vi.mocked(axios.patch).mockImplementation(async () => {
        server.find((item) => item.id === 'older-20')!.is_read = true
        return { data: {} }
      })
      vi.mocked(axios.post).mockImplementation(async () => {
        server.forEach((item) => {
          item.is_read = true
        })
        return { data: {} }
      })
      fetchMock.mockResolvedValue(
        createMockResponse([encodeSse(JSON.stringify({ notification: newest }), 'notification')], {
          hang: true,
        })
      )
      const wrapper = mount(NotificationBell)
      await vi.advanceTimersByTimeAsync(0)
      await flushPromises()
      server.unshift(newest)
      await openBell(wrapper)
      expect(wrapper.findAll('[data-notification-id]')).toHaveLength(21)
      expect(wrapper.get('[data-notification-id="older-20"]').text()).toContain('New')

      if (action === 'all') await markAllRead(wrapper)
      else {
        await wrapper.get('[data-notification-id="older-20"]').trigger('click')
        await flushPromises()
        await openBell(wrapper)
      }

      expect(wrapper.get('[data-notification-id="older-20"]').text()).not.toContain('New')
      wrapper.unmount()
    }
  )

  it('renders actionable notifications as buttons and informational ones as content', async () => {
    const wrapper = await mountAndOpen([actionableNotification, informationalNotification])

    const actionableRow = wrapper.get('[data-notification-id="act-1"]')
    expect(actionableRow.element.tagName).toBe('BUTTON')
    expect(actionableRow.attributes('type')).toBe('button')
    expect(actionableRow.find('[data-icon="mdi:chevron-right"]').exists()).toBe(true)

    const informationalRow = wrapper.get('[data-notification-id="info-1"]')
    expect(informationalRow.element.tagName).toBe('DIV')
    expect(informationalRow.attributes('type')).toBeUndefined()
    expect(informationalRow.text()).toContain('Informational Note')
    expect(informationalRow.find('[data-icon="mdi:chevron-right"]').exists()).toBe(false)

    await informationalRow.trigger('click')
    await flushPromises()
    expect(axios.patch).not.toHaveBeenCalled()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)

    await actionableRow.trigger('click')
    await settleClose()

    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/act-1/read', {})
    expect(mockPush).toHaveBeenCalledWith('/vault/vault-1/dwellers')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(wrapper.get('button[aria-haspopup="dialog"]').element)
    wrapper.unmount()
  })

  it('navigates and closes while the read request is still pending', async () => {
    const wrapper = await mountAndOpen([{ ...actionableNotification }])
    let resolvePatch!: (value: { data: object }) => void
    let settled = false
    vi.mocked(axios.patch).mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePatch = (value) => {
          settled = true
          resolve(value)
        }
      })
    )

    await wrapper.get('[data-notification-id="act-1"]').trigger('click')
    await settleClose()

    expect(mockPush).toHaveBeenCalledWith('/vault/vault-1/dwellers')
    expect(settled).toBe(false)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/act-1/read', {})
    expect(bellBadge(wrapper)).toBe('')

    resolvePatch({ data: {} })
    await flushPromises()
    wrapper.unmount()
  })

  it('renders the unread badge in the default theme color so the count stays readable', async () => {
    const wrapper = await mountBell([informationalNotification])

    expect(wrapper.get('button[aria-haspopup="dialog"]').attributes('aria-label')).toBe(
      'Notifications 1 unread'
    )
    const badge = wrapper.findAll('span').find((span) => span.text() === '1')
    // jsdom has no CSS pipeline: the translucent danger wash is unreadable on
    // the dark CRT shell, so the contrast requirement is pinned on the class attr.
    const badgeClass = badge?.attributes('class') ?? ''
    expect(badgeClass).toMatch(/(^|\s)bg-theme-primary(\s|$)/)
    expect(badgeClass).not.toMatch(/bg-danger\/20/)
    expect(badgeClass).toMatch(/(^|\s)text-black(\s|$)/)
    wrapper.unmount()
  })

  it('drops a delayed rush notification scheduled under a previous session', async () => {
    const auth = useAuthStore()
    signedIn()
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    useVaultStore().activeVaultId = 'vault-1'
    mockNotificationList([])
    const message = 'Rush succeeded'
    streamNotification(rushNotification('rush-1'))
    const wrapper = mount(NotificationBell, { attachTo: document.body })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(
      useNotificationInboxStore().recentNotifications.some((item) => item.id === 'rush-1')
    ).toBe(false)
    expect(toastsWith(message)).toHaveLength(0)
    wrapper.unmount()
  })

  it('cancels a pending rush notification when the bell unmounts', async () => {
    signedIn()
    mockNotificationList([])
    streamNotification(rushNotification('rush-2'))
    const wrapper = mount(NotificationBell, { attachTo: document.body })
    await vi.advanceTimersByTimeAsync(0)
    await flushPromises()

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(useNotificationInboxStore().recentNotifications).toEqual([])
  })

  it.each(['combat_victory', 'combat_defeat'])(
    'recovers an unread %s duel result once without double-counting it',
    async (notification_type) => {
      useToast().toasts.value = []
      const wrapper = await mountBell([
        notification({
          id: `duel-${notification_type}`,
          vault_id: 'vault-1',
          notification_type,
          title: 'Exhibition duel result',
          message: 'The duel result is ready to replay',
          is_read: false,
          meta_data: { duel_id: 'duel-1' },
        }),
      ])

      expect(toastsWith('The duel result is ready to replay')).toHaveLength(1)
      expect(useNotificationInboxStore().unreadCount).toBe(1)
      wrapper.unmount()
    }
  )
})
