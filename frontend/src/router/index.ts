import {
  createRouter,
  createWebHistory,
  type NavigationGuardNext,
  type RouteLocationNormalized
} from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useVaultStore } from '@/stores/vault'
import LoginScreen from '../components/LoginScreen.vue'
import VaultSelection from '../components/VaultSelection.vue'
import VaultInterface from '../components/VaultInterface.vue'

const routes = [
  {
    path: '/',
    name: 'Login',
    component: LoginScreen
  },
  {
    path: '/vaults',
    name: 'VaultSelection',
    component: VaultSelection,
    meta: { requiresAuth: true }
  },
  {
    path: '/vault/:id([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})',
    name: 'VaultInterface',
    component: VaultInterface,
    meta: { requiresAuth: true },
    async beforeEnter(
      to: RouteLocationNormalized,
      from: RouteLocationNormalized,
      next: NavigationGuardNext
    ) {
      const vaultStore = useVaultStore()
      const vaultId = to.params.id as string

      try {
        if (!vaultStore.vaults.length) {
          await vaultStore.fetchVaults()
        }

        if (vaultStore.selectVault(vaultId)) {
          next()
        } else {
          next('/vaults')
        }
      } catch (error) {
        console.error('Failed to fetch vaults:', error)
        next('/vaults')
      }
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const vaultStore = useVaultStore()

  try {
    if (to.meta.requiresAuth && !userStore.user.isAuthenticated) {
      next('/')
    } else if (to.name === 'VaultSelection' && !vaultStore.vaults.length) {
      await vaultStore.fetchVaults()
      next()
    } else {
      next()
    }
  } catch (error) {
    console.error('Navigation guard error:', error)
    next('/')
  }
})

export default router
