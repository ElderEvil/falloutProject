import { afterEach, describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../../helpers/mountWithSetup'
import { Toaster } from '@/core/components/ui/toast'
import { useToast } from '@/core/composables/useToast'

describe('Toaster', () => {
  let wrapper: ReturnType<typeof mountWithSetup> | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    const { toasts, remove } = useToast()
    while (toasts.value.length > 0) remove(toasts.value[0].id)
    document.body.innerHTML = ''
  })

  it('renders no toasts when the toast queue is empty', () => {
    wrapper = mountWithSetup(Toaster)

    expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(0)
  })

  it('renders active toasts into the body with a polite status', () => {
    useToast().show('Vault saved', 'success')
    wrapper = mountWithSetup(Toaster)

    const status = document.body.querySelector('[role="status"]')
    expect(status).not.toBeNull()
    expect(status?.textContent).toContain('Vault saved')
    expect(status?.getAttribute('aria-live')).toBe('polite')
  })

  it('renders multiple toasts in arrival order', () => {
    useToast().show('First message', 'info')
    useToast().show('Second message', 'warning')
    wrapper = mountWithSetup(Toaster)

    const statuses = document.body.querySelectorAll('[role="status"]')
    expect(statuses).toHaveLength(2)
    expect(statuses[0]?.textContent).toContain('First message')
    expect(statuses[1]?.textContent).toContain('Second message')
  })

  it('removes a toast when its close button is clicked', async () => {
    useToast().show('Dismiss me', 'info')
    wrapper = mountWithSetup(Toaster)

    const closeButton = document.body.querySelector<HTMLButtonElement>('[aria-label="Close"]')
    expect(closeButton).not.toBeNull()
    closeButton!.click()

    // Let the leave transition finish before asserting the toast is gone.
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(document.body.querySelectorAll('[role="status"]')).toHaveLength(0)
    expect(useToast().toasts.value).toHaveLength(0)
  })
})
