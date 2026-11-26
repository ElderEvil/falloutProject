import type { RouteRecordRaw } from 'vue-router'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

export const pvpRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/pvp',
    name: 'vault-raids',
    component: () => import('../views/VaultRaidsView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
    beforeEnter: async (to) => {
      const flags = useFeatureFlagsStore()
      if (!flags.loaded) await flags.fetchFlags()
      if (!flags.pvpDuels) return { name: 'vault', params: { id: to.params.id } }
      return true
    },
  },
]
