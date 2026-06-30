import type { RouteRecordRaw } from 'vue-router'

export const progressionRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/training',
    name: 'training',
    component: () => import('../views/TrainingView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
  },
  {
    path: '/vault/:id/quests',
    name: 'quests',
    component: () => import('../views/QuestsView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
  },
  {
    path: '/vault/:id/quests/:questId',
    name: 'quest-detail',
    component: () => import('../views/QuestDetailView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id/quests' },
  },
  {
    path: '/vault/:id/objectives',
    name: 'objectives',
    component: () => import('../views/ObjectivesView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
  },
]
