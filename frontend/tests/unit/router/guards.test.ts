import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import LoginForm from '@/components/auth/LoginForm.vue'

describe('Router Guards', () => {
  let router: any
  let authStore: any

  beforeEach(async () => {
    setActivePinia(createPinia())
    authStore = useAuthStore()

    // Create test router with same routes as main router
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          name: 'home',
          component: HomeView,
          meta: { requiresAuth: true }
        },
        {
          path: '/vault',
          name: 'vault',
          component: { template: '<div>Vault</div>' },
          meta: { requiresAuth: true }
        },
        {
          path: '/login',
          name: 'login',
          component: LoginForm
        },
        {
          path: '/public',
          name: 'public',
          component: { template: '<div>Public</div>' }
        }
      ]
    })

    // Add the same guard as main router
    router.beforeEach((to: any, from: any, next: any) => {
      const authStore = useAuthStore()
      if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        next('/login')
      } else {
        next()
      }
    })

    await router.isReady()
  })

  describe('Authentication Guard', () => {
    it('should allow access to public routes without authentication', async () => {
      authStore.token = null
      await router.push('/public')

      expect(router.currentRoute.value.path).toBe('/public')
    })

    it('should allow access to login page without authentication', async () => {
      authStore.token = null
      await router.push('/login')

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should redirect to login when accessing protected route without auth', async () => {
      authStore.token = null
      await router.push('/')

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should allow access to protected routes when authenticated', async () => {
      authStore.token = 'test-token'
      await router.push('/')

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('should allow navigation between protected routes when authenticated', async () => {
      authStore.token = 'test-token'
      await router.push('/')
      await router.push('/vault')

      expect(router.currentRoute.value.path).toBe('/vault')
    })

    it('should redirect to login when token is removed', async () => {
      authStore.token = 'test-token'
      await router.push('/')
      expect(router.currentRoute.value.path).toBe('/')

      authStore.token = null
      await router.push('/vault')

      expect(router.currentRoute.value.path).toBe('/login')
    })
  })

  describe('Route Meta', () => {
    it('home route should require authentication', () => {
      const homeRoute = router.getRoutes().find((r: any) => r.name === 'home')
      expect(homeRoute?.meta.requiresAuth).toBe(true)
    })

    it('vault route should require authentication', () => {
      const vaultRoute = router.getRoutes().find((r: any) => r.name === 'vault')
      expect(vaultRoute?.meta.requiresAuth).toBe(true)
    })

    it('login route should not require authentication', () => {
      const loginRoute = router.getRoutes().find((r: any) => r.name === 'login')
      expect(loginRoute?.meta.requiresAuth).toBeUndefined()
    })
  })
})
