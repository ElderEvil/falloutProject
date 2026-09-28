import type { RouteRecordRaw } from 'vue-router'

const ResponseTeamsView = () => import('../views/ResponseTeamsView.vue')

export const contaminationTeamRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/response-teams',
    name: 'response-teams',
    component: ResponseTeamsView,
    meta: { requiresAuth: true, hideFromNav: true, parentRoute: '/vault/:id' },
  },
]

export default contaminationTeamRoutes