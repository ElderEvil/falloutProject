import type { RouteRecordRaw } from 'vue-router'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

export const envoyRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/envoy',
    name: 'envoyTerminal',
    component: () => import('../views/EnvoyView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
    beforeEnter: async (to) => {
      const flags = useFeatureFlagsStore()
      if (!flags.loaded) await flags.fetchFlags()
      if (!flags.vaultDiplomacy) return { name: 'vault', params: { id: to.params.id } }
      return true
    },
  },
  {
    // Old links and bookmarks keep working; the Trading Post is the LABOUR tab now.
    path: '/vault/:id/trading',
    redirect: (to) => ({ name: 'envoyTerminal', params: { id: to.params.id } }),
  },
]
