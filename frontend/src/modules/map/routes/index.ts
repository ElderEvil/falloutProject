import type { RouteRecordRaw } from 'vue-router'

export const mapRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/map',
    name: 'vault-map',
    component: () => import('../views/MapView.vue'),
    meta: { requiresAuth: true },
  },
]
