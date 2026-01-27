import type { RouteRecordRaw } from 'vue-router'

export const progressionRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/training',
    name: 'training',
    component: () => import('../views/TrainingView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/vault/:id/quests',
    name: 'quests',
    component: () => import('../views/QuestsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/vault/:id/objectives',
    name: 'objectives',
    component: () => import('../views/ObjectivesView.vue'),
    meta: { requiresAuth: true },
  },
]
