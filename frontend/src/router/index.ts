import { createRouter, createWebHistory, type RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Module routes
import { authRoutes } from '@/modules/auth/routes'
import { vaultRoutes } from '@/modules/vault/routes'
import { profileRoutes } from '@/modules/profile/routes'
import { chatRoutes } from '@/modules/chat/routes'
import { explorationRoutes } from '@/modules/exploration/routes'
import { mapRoutes } from '@/modules/map/routes'
import { progressionRoutes } from '@/modules/progression/routes'
import { socialRoutes } from '@/modules/social/routes'
import { dwellersRoutes } from '@/modules/dwellers/routes'
import { storageRoutes } from '@/modules/storage/routes'
import { aiSettingsRoutes } from '@/modules/ai-settings/routes'
import { tradingRoutes } from '@/modules/trading/routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Vault module routes (includes home, vault, happiness)
    ...vaultRoutes,
    // Dweller module routes
    ...dwellersRoutes,
    // Chat module routes
    ...chatRoutes,
    // Exploration module routes
    ...explorationRoutes,
    // Map module routes
    ...mapRoutes,
    // Storage module routes
    ...storageRoutes,
    // Trading Post module routes
    ...tradingRoutes,
    // Progression module routes (training, quests, objectives)
    ...progressionRoutes,
    // Radio module routes
    // Social module routes (relationships)
    ...socialRoutes,
    // Profile module routes
    ...profileRoutes,
    // AI settings (admin)
    ...aiSettingsRoutes,
    // Auth module routes
    ...authRoutes,
    // Dev-only UI catalog — compiled out of production builds (import.meta.env.DEV
    // is statically replaced with false by Vite), never linked from any nav.
    ...(import.meta.env.DEV
      ? [
          {
            path: '/dev/ui-catalog',
            name: 'ui-catalog',
            component: () => import('@/core/views/UiCatalogView.vue'),
          },
        ]
      : []),
    {
      path: '/about',
      name: 'about',
      // Lazy-load the AboutView component
      component: () => import('@/modules/profile/views/AboutView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return '/login'
  }
  if (to.meta.requiresSuperuser && !authStore.isSuperuser) {
    return '/profile'
  }
  return true
})

// Suppress route not found and duplicate-navigation warnings, re-throw everything else
const originalPush = router.push.bind(router)
router.push = function push(location: RouteLocationRaw) {
  return originalPush(location).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err)
    if (message === 'NavigationDuplicated' || message.includes('No match found')) {
      return Promise.resolve()
    }
    console.warn('[Vue Router]', message)
    throw err
  })
}

export default router
