import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import { useAuthStore } from '@/modules/auth/stores/auth'
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

describe('Map route', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('route resolution', () => {
    it('resolves /vault/abc/map to vault-map with requiresAuth', () => {
      const resolved = router.resolve('/vault/abc/map')
      expect(resolved.name).toBe('vault-map')
      expect(resolved.meta.requiresAuth).toBe(true)
    })
  })

  describe('auth guard', () => {
    it('redirects unauthenticated navigation to login', async () => {
      // No token set → isAuthenticated is false
      await router.push('/vault/abc/map')
      // The beforeEach guard returns '/login' for unauthenticated auth-required routes
      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('allows authenticated navigation', async () => {
      // Set a token so isAuthenticated is true
      localStorage.setItem('token', 'test-token')
      // Re-create the auth store to pick up the token
      const store = useAuthStore()
      expect(store.isAuthenticated).toBe(true)

      await router.push('/vault/abc/map')
      expect(router.currentRoute.value.name).toBe('vault-map')
    })
  })

  describe('SidePanel nav item', () => {
    it('contains a nav item with id map', () => {
      const wrapper = shallowMount(SidePanel, {
        global: {
          stubs: {
            Icon: true,
            UTooltip: true,
          },
        },
      })
      const navItems = wrapper.vm.navItems
      expect(navItems).toBeDefined()
      const mapItem = navItems.find((item: { id: string }) => item.id === 'map')
      expect(mapItem).toBeDefined()
      expect(mapItem!.label).toBe('Map')
      expect(mapItem!.icon).toBe('mdi:map')
      expect(mapItem!.path).toBe('/vault/vault-1/map')
      expect(mapItem!.hotkey).toBeUndefined()
    })
  })
})
