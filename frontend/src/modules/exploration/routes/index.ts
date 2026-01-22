import type { RouteRecordRaw } from 'vue-router'

export const explorationRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/exploration',
    name: 'exploration',
    component: () => import('../views/ExplorationView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/vault/:id/exploration/:explorationId',
    name: 'exploration-detail',
    component: () => import('../views/ExplorationDetailView.vue'),
    meta: { requiresAuth: true }
  }
]
