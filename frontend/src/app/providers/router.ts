import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/features/auth/store/auth'
import { useVaultStore } from '@/stores/vault'
import { ROUTES } from '@/shared/config'

const routes = [
  {
    path: ROUTES.LOGIN,
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue')
  },
  {
    path: ROUTES.VAULTS,
    name: 'VaultSelection',
    component: () => import('@/pages/VaultSelectionPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: ROUTES.VAULT_DETAILS,
    name: 'VaultInterface',
    component: () => import('@/pages/VaultInterfacePage.vue'),
    meta: { requiresAuth: true },
    async beforeEnter(to, from, next) {
      const vaultStore = useVaultStore()
      const vaultId = parseInt(to.params.id as string)

      if (!vaultStore.vaults.length) {
        await vaultStore.fetchVaults()
      }

      if (vaultStore.selectVault(vaultId)) {
        next()
      } else {
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
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()

  if (to.meta.requiresAuth && !authStore.user.isAuthenticated) {
    next('/')
  } else if (to.name === 'VaultSelection' && !vaultStore.vaults.length) {
    await vaultStore.fetchVaults()
    next()
  } else {
    next()
  }
})

export default router
