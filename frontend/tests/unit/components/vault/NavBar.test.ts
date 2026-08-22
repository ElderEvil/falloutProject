import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NavBar from '@/modules/vault/components/shell/NavBar.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { User } from '@/modules/auth/types/user'

vi.mock('@/core/composables/useVersionDetection', () => ({
  useVersionDetection: () => ({
    versionBadgeVisible: { value: false },
    showChangelog: vi.fn(),
  }),
}))

const testUser: User = {
  id: 'user-1',
  username: 'Overseer',
  email: 'overseer@example.com',
  is_active: true,
  is_superuser: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('NavBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses a terminal-green highlight for user menu items', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: {
          Icon: true,
          NotificationBell: true,
        },
      },
    })

    await wrapper.find('button[aria-label="User menu for Overseer"]').trigger('click')

    const profileItem = wrapper.find('a[aria-label="View profile"]')
    expect(profileItem.classes()).toContain('hover:bg-theme-primary/10')
    expect(profileItem.classes()).toContain('focus:bg-theme-primary/15')
    expect(profileItem.classes()).not.toContain('hover:bg-gray-900')
  })

  it('marks the profile control active on the profile route', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profile', component: { template: '<div />' } }],
    })
    await router.push('/profile')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    expect(wrapper.find('button[aria-label="User menu for Overseer"]').classes()).toContain(
      'bg-theme-primary/10'
    )
  })
})
