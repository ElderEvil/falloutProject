import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
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

  it('should have role="dialog" on the modal content', async () => {
    mountModal()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).toBeTruthy()
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
})
