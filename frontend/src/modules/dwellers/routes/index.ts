import type { RouteRecordRaw } from 'vue-router'

export const dwellersRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/dwellers',
    name: 'dwellers',
    component: () => import('../views/DwellersView.vue'),
    meta: { requiresAuth: true, hideFromNav: true },
  },
  {
    path: '/vault/:id/dwellers/graveyard',
    name: 'graveyard',
    component: () => import('../views/GraveyardView.vue'),
    meta: { requiresAuth: true, hideFromNav: true, parentRoute: '/vault/:id/dwellers' },
  },
  {
    path: '/vault/:id/dwellers/:dwellerId',
    name: 'dwellerDetail',
    component: () => import('../views/DwellerDetailView.vue'),
    meta: { requiresAuth: true, hideFromNav: true, parentRoute: '/vault/:id/dwellers' },
  },
  {
    path: '/design/dweller-panels',
    name: 'dwellerPanelLab',
    component: () => import('../views/PanelHeaderLabView.vue'),
    meta: { hideFromNav: true },
  },
  {
    path: '/design/dweller-page',
    name: 'dwellerPageLab',
    component: () => import('../views/DwellerPageLabView.vue'),
    meta: { hideFromNav: true },
  },
]
