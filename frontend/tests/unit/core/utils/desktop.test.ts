import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isTauri } from '@tauri-apps/api/core'
import { resolveResource } from '@tauri-apps/api/path'
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from '@tauri-apps/plugin-notification'
import { openUrl } from '@tauri-apps/plugin-opener'
import { handleStoreError } from '@/core/utils/errorHandler'
import { initializeDesktop, notifyDesktop, openExternalUrl } from '@/core/utils/desktop'

vi.mock('@tauri-apps/api/core', () => ({ isTauri: vi.fn() }))
vi.mock('@tauri-apps/api/path', () => ({ resolveResource: vi.fn() }))
vi.mock('@tauri-apps/plugin-notification', () => ({
  isPermissionGranted: vi.fn(),
  requestPermission: vi.fn(),
  sendNotification: vi.fn(),
}))
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn() }))
vi.mock('@/core/utils/errorHandler', () => ({ handleStoreError: vi.fn() }))

describe('desktop operating-system boundary', () => {
  const notification = { title: 'Training complete', message: 'Strength increased' }

  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(isTauri).mockReturnValue(true)
    vi.mocked(resolveResource).mockResolvedValue('/resources/notification-icon.png')
    vi.mocked(isPermissionGranted).mockResolvedValue(true)
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
  })

  afterEach(() => vi.restoreAllMocks())

  it('delivers a hidden desktop alert when permission is granted', async () => {
    await notifyDesktop(notification, () => true)
    expect(sendNotification).toHaveBeenCalledExactlyOnceWith({
      title: notification.title,
      body: notification.message,
      icon: '/resources/notification-icon.png',
    })
  })

  it('does not send operating-system alerts in the browser or a visible window', async () => {
    vi.mocked(isTauri).mockReturnValue(false)
    await notifyDesktop(notification, () => true)
    vi.mocked(isTauri).mockReturnValue(true)
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    await notifyDesktop(notification, () => true)
    expect(isPermissionGranted).not.toHaveBeenCalled()
    expect(sendNotification).not.toHaveBeenCalled()
  })

  it('respects denied permission without prompting from a background event', async () => {
    vi.mocked(isPermissionGranted).mockResolvedValue(false)
    await notifyDesktop(notification, () => true)
    expect(sendNotification).not.toHaveBeenCalled()
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it.each(['session changed', 'window shown'])(
    'drops delayed delivery after %s',
    async (reason) => {
      let resolvePermission!: (granted: boolean) => void
      const pending = new Promise<boolean>((resolve) => {
        resolvePermission = resolve
      })
      vi.mocked(isPermissionGranted).mockReturnValue(pending)
      let current = true
      const delivery = notifyDesktop(notification, () => current)
      // Let the lazy OS-plugin import reach the pending permission check.
      await vi.waitFor(() => expect(isPermissionGranted).toHaveBeenCalled())
      if (reason === 'session changed') current = false
      else vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
      resolvePermission(true)
      await delivery
      expect(sendNotification).not.toHaveBeenCalled()
    }
  )

  it('logs a failed native delivery without rejecting the bell delivery path', async () => {
    vi.mocked(isPermissionGranted).mockRejectedValue(new Error('OS unavailable'))
    await expect(notifyDesktop(notification, () => true)).resolves.toBeUndefined()
    expect(handleStoreError).toHaveBeenCalled()
  })

  it('opens only HTTP(S) links through the native opener', async () => {
    await openExternalUrl('https://github.com/ElderEvil/falloutProject')
    await openExternalUrl('file:///etc/passwd')
    await openExternalUrl('javascript:alert(1)')
    expect(openUrl).toHaveBeenCalledExactlyOnceWith('https://github.com/ElderEvil/falloutProject')
  })

  it('handles malformed links without an unhandled rejection', async () => {
    await expect(openExternalUrl('not a URL')).resolves.toBeUndefined()
    expect(openUrl).not.toHaveBeenCalled()
    expect(handleStoreError).toHaveBeenCalled()
  })

  it('opens middle-clicked external links in the system browser', async () => {
    const listeners = vi.spyOn(document, 'addEventListener')
    const anchor = document.createElement('a')
    anchor.href = 'https://github.com/ElderEvil/falloutProject'
    document.body.append(anchor)
    try {
      await initializeDesktop()
      const event = new MouseEvent('auxclick', { button: 1, bubbles: true, cancelable: true })
      anchor.dispatchEvent(event)
      expect(event.defaultPrevented).toBe(true)
      await vi.waitFor(() => expect(openUrl).toHaveBeenCalledExactlyOnceWith(anchor.href))
    } finally {
      anchor.remove()
      for (const [type, listener, options] of listeners.mock.calls) {
        if (type === 'click' || type === 'auxclick')
          document.removeEventListener(type, listener, options)
      }
    }
  })
})
