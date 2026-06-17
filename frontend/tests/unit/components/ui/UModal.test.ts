import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UModal from '@/core/components/ui/UModal.vue'

describe('UModal (Accessibility)', () => {
  const mountModal = () =>
    mount(UModal, {
      props: { modelValue: true, title: 'Test Modal' },
      slots: { default: '<p class="modal-body">Modal body</p>' },
      attachTo: document.body,
    })

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
