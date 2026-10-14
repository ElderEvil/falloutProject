import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import router from '@/router'
import SidePanel from '@/core/components/common/SidePanel.vue'

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({
    isCollapsed: { value: false },
    toggle: vi.fn(),
  }),
}))

const mockPush = vi.fn()
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: mockPush,
    }),
    useRoute: () => ({
      params: { id: 'vault-1' },
      path: '/vault/vault-1',
    }),
  }
})

describe('Response teams route', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('route resolution', () => {
    it('resolves /vault/abc/response-teams to response-teams with requiresAuth', () => {
      const resolved = router.resolve('/vault/abc/response-teams')
      expect(resolved.name).toBe('response-teams')
      expect(resolved.meta.requiresAuth).toBe(true)
    })
  })

  describe('SidePanel nav item', () => {
    it('no longer advertises a Response Teams nav entry', () => {
      const wrapper = shallowMount(SidePanel, {
        global: {
          stubs: {
            Icon: true,
            Tooltip: true,
          },
        },
      })
      const navItems = wrapper.vm.navItems
      expect(navItems).toBeDefined()
      expect(navItems.some((entry: { id: string }) => entry.id === 'response-teams')).toBe(false)
    })
  })
})
