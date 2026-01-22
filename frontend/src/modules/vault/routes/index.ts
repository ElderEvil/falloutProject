import type { RouteRecordRaw } from 'vue-router'

// Eager load home view for fastest initial load
import HomeView from '../views/HomeView.vue'

const VaultView = () => import('../views/VaultView.vue')
const HappinessView = () => import('../views/HappinessView.vue')

export const vaultRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { requiresAuth: true, hideFromNav: false }
  },
  {
    path: '/vault/:id',
    name: 'vault',
    component: VaultView,
    meta: { requiresAuth: true, hideFromNav: true }
  },
  {
    path: '/vault/:id/happiness',
    name: 'happiness',
    component: HappinessView,
    meta: { requiresAuth: true, hideFromNav: true }
  }
]

export default vaultRoutes
