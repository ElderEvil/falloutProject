import type { RouteRecordRaw } from 'vue-router'

export const tradingRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/trading',
    name: 'tradingPost',
    component: () => import('../views/TradingPostView.vue'),
    meta: { requiresAuth: true, hideFromNav: true },
  },
]
