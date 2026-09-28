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
    it('contains a nav item with id response-teams', () => {
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
      const item = navItems.find((entry: { id: string }) => entry.id === 'response-teams')
      expect(item).toBeDefined()
      expect(item!.label).toBe('Response Teams')
      expect(item!.icon).toBe('mdi:account-hard-hat')
      expect(item!.path).toBe('/vault/vault-1/response-teams')
      expect(item!.hotkey).toBeUndefined()
    })
  })
})