import type { RouteRecordRaw } from 'vue-router'

export const storageRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/storage',
    name: 'VaultStorage',
    component: () => import('./views/StorageView.vue'),
    meta: { requiresAuth: true },
  },
]
