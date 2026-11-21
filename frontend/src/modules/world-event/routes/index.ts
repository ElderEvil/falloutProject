import type { RouteRecordRaw } from 'vue-router'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

export const worldEventRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/world-event',
    name: 'world-event',
    component: () => import('../views/WorldEventView.vue'),
    meta: { requiresAuth: true, hideFromNav: true, parentRoute: '/vault/:id' },
    beforeEnter: async (to) => {
      const flags = useFeatureFlagsStore()
      if (!flags.loaded) await flags.fetchFlags()
      if (!flags.worldEvents) return { name: 'vault', params: { id: to.params.id } }
      return true
    },
  },
]

export default worldEventRoutes
