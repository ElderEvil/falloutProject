import { nextTick, onUnmounted, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])'

let scrollLockCount = 0
let previousBodyOverflow = ''

interface Options {
  focusTarget: Ref<HTMLElement | null>
  closeOnEscape?: MaybeRefOrGetter<boolean>
}

const lockBodyScroll = () => {
  if (scrollLockCount === 0) previousBodyOverflow = document.body.style.overflow
  scrollLockCount += 1
  document.body.style.overflow = 'hidden'
}

const unlockBodyScroll = () => {
  if (scrollLockCount === 0) return
  scrollLockCount -= 1
  if (scrollLockCount === 0) document.body.style.overflow = previousBodyOverflow
}

export function useModalBehavior(
  isOpen: MaybeRefOrGetter<boolean>,
  close: () => void,
  { focusTarget, closeOnEscape = true }: Options,
) {
  let previousActiveElement: HTMLElement | null = null
  let isLocked = false

  const getFocusableElements = (): HTMLElement[] =>
    focusTarget.value
      ? Array.from(focusTarget.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      : []

  const focusInitialElement = () => {
    const [firstElement] = getFocusableElements()
    const initialElement = firstElement ?? focusTarget.value
    initialElement?.focus()
  }

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && toValue(closeOnEscape)) {
      event.stopPropagation()
      close()
      return
    }

    if (event.key !== 'Tab') return

    const elements = getFocusableElements()
    if (elements.length === 0) {
      event.preventDefault()
      return
    }

    const firstElement = elements[0]!
    const lastElement = elements[elements.length - 1]!
    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault()
      lastElement.focus()
    } else if (
      !event.shiftKey &&
      (document.activeElement === lastElement || !focusTarget.value?.contains(document.activeElement))
    ) {
      event.preventDefault()
      firstElement.focus()
    }
  }

  const cleanup = () => {
    if (isLocked) {
      unlockBodyScroll()
      isLocked = false
    }
    if (previousActiveElement && document.body.contains(previousActiveElement)) {
      previousActiveElement.focus()
    }
    previousActiveElement = null
  }

  watch(
    () => toValue(isOpen),
    async (open) => {
      if (!open) {
        cleanup()
        return
      }

      previousActiveElement = document.activeElement as HTMLElement | null
      lockBodyScroll()
      isLocked = true
      await nextTick()
      if (toValue(isOpen)) focusInitialElement()
    },
    { immediate: true },
  )

  onUnmounted(cleanup)

  return { handleKeydown }
}
