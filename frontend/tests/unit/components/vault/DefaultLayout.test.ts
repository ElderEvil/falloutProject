import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import DefaultLayout from '@/modules/vault/components/shell/DefaultLayout.vue'

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}))

const mountLayout = (scanlines?: boolean) =>
  mount(DefaultLayout, {
    props: { isFlickering: false },
    global: {
      provide: scanlines === undefined ? {} : { scanlines: ref(scanlines) },
      stubs: { NavBar: true, ExitRequestModal: true },
    },
  })

describe('DefaultLayout', () => {
  it('renders exactly one scanline overlay when the preference is enabled', () => {
    expect(mountLayout(true).findAll('.scanlines')).toHaveLength(1)
  })

  it('renders no scanline overlay when the preference is disabled', () => {
    expect(mountLayout(false).find('.scanlines').exists()).toBe(false)
  })

  it('defaults the overlay to enabled when no preference is provided', () => {
    expect(mountLayout().findAll('.scanlines')).toHaveLength(1)
  })
})
