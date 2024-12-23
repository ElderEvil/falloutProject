import { createRouter, createWebHistory } from 'vue-router'
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
    path: '/vault/:id',
    name: 'VaultInterface',
    component: VaultInterface,
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
  const userStore = useUserStore()
  const vaultStore = useVaultStore()

  if (to.meta.requiresAuth && !userStore.user.isAuthenticated) {
    next('/')
  } else if (to.name === 'VaultSelection' && !vaultStore.vaults.length) {
    await vaultStore.fetchVaults()
    next()
  } else {
    next()
  }
})

export default router
