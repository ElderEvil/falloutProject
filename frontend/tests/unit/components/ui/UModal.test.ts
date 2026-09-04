import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import UModal from '@/core/components/ui/UModal.vue'

describe('UModal (Accessibility)', () => {
  let wrapper: ReturnType<typeof mount> | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  const mountModal = () => {
    wrapper = mount(UModal, {
      props: { modelValue: true, title: 'Test Modal' },
      slots: { default: '<p class="modal-body">Modal body</p>' },
      attachTo: document.body,
    })
    return wrapper
  }

  it('should make the modal content a focusable dialog root', async () => {
    mountModal()
    const dialog = document.querySelector('[role="dialog"]')
    expect([dialog?.getAttribute('role'), dialog?.getAttribute('tabindex')]).toEqual(['dialog', '-1'])
  })

  it('should have aria-modal="true" on the modal content', async () => {
    mountModal()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.getAttribute('aria-modal')).toBe('true')
  })

  it('should not have inline style on the modal content border', async () => {
    mountModal()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.getAttribute('style')).toBeFalsy()
  })

  it('gives the close button a visible keyboard focus style', () => {
    mountModal()
    expect(document.querySelector<HTMLButtonElement>('[aria-label="Close modal"]')?.classList).toContain('focus-visible:outline-2')
  })

  it('uses the requested warm surface role', () => {
    wrapper = mount(UModal, {
      props: { modelValue: true, title: 'Map marker', surface: 'base' },
      attachTo: document.body,
    })

    expect(document.querySelector('[role="dialog"]')?.classList).toContain('bg-surface')
  })

  it('restores focus and existing body overflow when closed', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    document.body.style.overflow = 'auto'

    wrapper = mount(UModal, {
      props: { modelValue: true, title: 'Test Modal' },
      attachTo: document.body,
    })
    await nextTick()

    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ modelValue: false })

    expect(document.body.style.overflow).toBe('auto')
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
    document.body.style.overflow = ''
  })
})
