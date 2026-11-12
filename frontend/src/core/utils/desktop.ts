import { isTauri } from '@tauri-apps/api/core'
import { handleStoreError } from '@/core/utils/errorHandler'

export const isDesktop = () => isTauri()

export async function openExternalUrl(url: string): Promise<void> {
  try {
    if (!['http:', 'https:'].includes(new URL(url).protocol)) return
    if (isDesktop()) {
      const { openUrl } = await import('@tauri-apps/plugin-opener')
      await openUrl(url)
    } else {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    handleStoreError(error, 'Unable to open external link')
  }
}

export async function notifyDesktop(
  notification: { title: string; message: string },
  ownsSession: () => boolean
): Promise<void> {
  if (!isDesktop() || document.visibilityState !== 'hidden' || !ownsSession()) return
  try {
    const { isPermissionGranted, sendNotification } =
      await import('@tauri-apps/plugin-notification')
    if (!(await isPermissionGranted())) return
    const { resolveResource } = await import('@tauri-apps/api/path')
    const icon = await resolveResource('notification-icon.png')
    if (document.visibilityState !== 'hidden' || !ownsSession()) return
    sendNotification({ title: notification.title, body: notification.message, icon })
  } catch (error) {
    // OS delivery is optional; the existing bell/toast delivery must keep working.
    handleStoreError(error, 'Unable to send desktop notification', false)
  }
}

export async function initializeDesktop(): Promise<void> {
  if (!isDesktop()) return
  const openExternalLink = (event: MouseEvent) => {
    if (
      event.defaultPrevented ||
      ![0, 1].includes(event.button) ||
      !(event.target instanceof Element)
    )
      return
    const anchor = event.target.closest('a[href]')
    if (!(anchor instanceof HTMLAnchorElement) || anchor.hasAttribute('download')) return
    const url = new URL(anchor.href)
    if (!['http:', 'https:'].includes(url.protocol) || url.origin === window.location.origin) return
    event.preventDefault()
    void openExternalUrl(url.href)
  }
  document.addEventListener('click', openExternalLink)
  document.addEventListener('auxclick', openExternalLink)
  try {
    const { isPermissionGranted, requestPermission } =
      await import('@tauri-apps/plugin-notification')
    if (!(await isPermissionGranted())) await requestPermission()
  } catch (error) {
    handleStoreError(error, 'Unable to initialize desktop notifications', false)
  }
}
