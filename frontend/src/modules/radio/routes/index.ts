import type { RouteRecordRaw } from 'vue-router'

const RadioView = () => import('../views/RadioView.vue')

export const radioRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/radio',
    name: 'radio',
    component: RadioView,
    meta: { requiresAuth: true, hideFromNav: true },
  },
]

export default radioRoutes
