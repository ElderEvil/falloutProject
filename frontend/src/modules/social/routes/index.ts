import type { RouteRecordRaw } from 'vue-router'

export const socialRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/relationships',
    name: 'relationships',
    component: () => import('../views/RelationshipsView.vue'),
    meta: { requiresAuth: true }
  }
]
