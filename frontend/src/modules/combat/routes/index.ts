import type { RouteRecordRaw } from 'vue-router'

export const combatRoutes: RouteRecordRaw[] = import.meta.env.DEV
  ? [
      {
        path: '/playground/incidents',
        name: 'incidentPlayground',
        component: () => import('../views/IncidentPlaygroundView.vue'),
        meta: { requiresAuth: true, hideFromNav: true },
      },
    ]
  : []
