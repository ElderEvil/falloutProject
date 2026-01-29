import { ref } from 'vue'

export interface Toast {
  id: string
  message: string
  variant: 'success' | 'error' | 'warning' | 'info'
  duration?: number
  count?: number
}

const toasts = ref<Toast[]>([])
let toastId = 0
const MAX_TOASTS = 5
const timeoutHandles = new Map<string, ReturnType<typeof setTimeout>>()

const DEFAULT_DURATIONS: Record<Toast['variant'], number> = {
  success: 3000,
  info: 5000,
  warning: 7000,
  error: 0,
}

function getGroupKey(variant: Toast['variant'], message: string): string {
  return `${variant}:${message}`
}

function clearTimeout(id: string): void {
  const handle = timeoutHandles.get(id)
  if (handle !== undefined) {
    globalThis.clearTimeout(handle)
    timeoutHandles.delete(id)
  }
}

export function useToast() {
  const show = (message: string, variant: Toast['variant'] = 'info', duration?: number) => {
    const finalDuration = duration !== undefined ? duration : DEFAULT_DURATIONS[variant]

    const groupKey = getGroupKey(variant, message)

    const existingIndex = toasts.value.findIndex(
      (t) => getGroupKey(t.variant, t.message) === groupKey
    )

    if (existingIndex !== -1) {
      const existingToast = toasts.value[existingIndex]
      existingToast.count = (existingToast.count ?? 1) + 1

      clearTimeout(existingToast.id)

      if (finalDuration > 0) {
        const handle = setTimeout(() => {
          remove(existingToast.id)
        }, finalDuration)
        timeoutHandles.set(existingToast.id, handle)
      }

      return existingToast.id
    }

    const id = `toast-${toastId++}`
    const toast: Toast = { id, message, variant, duration: finalDuration, count: 1 }

    if (toasts.value.length >= MAX_TOASTS) {
      const oldestToast = toasts.value.shift()
      if (oldestToast) {
        clearTimeout(oldestToast.id)
      }
    }

    toasts.value.push(toast)

    if (finalDuration > 0) {
      const handle = setTimeout(() => {
        remove(id)
      }, finalDuration)
      timeoutHandles.set(id, handle)
    }

    return id
  }

  const remove = (id: string) => {
    const index = toasts.value.findIndex((t) => t.id === id)
    if (index !== -1) {
      clearTimeout(id)
      toasts.value.splice(index, 1)
    }
  }

  const success = (message: string, duration?: number) => show(message, 'success', duration)
  const error = (message: string, duration?: number) => show(message, 'error', duration)
  const warning = (message: string, duration?: number) => show(message, 'warning', duration)
  const info = (message: string, duration?: number) => show(message, 'info', duration)

  return {
    toasts,
    show,
    remove,
    success,
    error,
    warning,
    info,
  }
}
