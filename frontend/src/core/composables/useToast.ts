import { useToast as useNuxtUiToast } from '@nuxt/ui/composables'

let nuxtToast: ReturnType<typeof useNuxtUiToast> | null = null

export function useToast() {
  if (!nuxtToast) {
    nuxtToast = useNuxtUiToast()
  }

  const toast = nuxtToast

  const show = (
    message: string,
    variant: 'success' | 'error' | 'warning' | 'info' = 'info',
    duration?: number
  ) => {
    const t = toast.add({
      title: message,
      color: variant,
      timeout: duration,
    })
    return String(t.id)
  }

  const remove = (id: string | number) => {
    toast.remove(id)
  }

  const success = (message: string, duration?: number) => show(message, 'success', duration)
  const error = (message: string, duration?: number) => show(message, 'error', duration)
  const warning = (message: string, duration?: number) => show(message, 'warning', duration)
  const info = (message: string, duration?: number) => show(message, 'info', duration)

  return {
    show,
    remove,
    success,
    error,
    warning,
    info,
  }
}
