import type { RouteRecordRaw } from 'vue-router'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

export const messagesRoutes: RouteRecordRaw[] = [
  {
    path: '/vault/:id/messages',
    name: 'messages',
    component: () => import('../views/MessagesView.vue'),
    meta: { requiresAuth: true, parentRoute: '/vault/:id' },
    beforeEnter: async (to) => {
      const featureFlags = useFeatureFlagsStore()
      if (!featureFlags.loaded) await featureFlags.fetchFlags()
      if (!featureFlags.playerConnections) {
        return { name: 'vault', params: { id: String(to.params.id) } }
      }
      return true
    },
  },
]
