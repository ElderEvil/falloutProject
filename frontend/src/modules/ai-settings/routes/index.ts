import type { RouteRecordRaw } from 'vue-router'

const AISettingsView = () => import('../views/AISettingsView.vue')

export const aiSettingsRoutes: RouteRecordRaw[] = [
  {
    path: '/admin/ai-settings',
    name: 'ai-settings',
    component: AISettingsView,
    meta: { requiresAuth: true, requiresSuperuser: true, hideFromNav: true },
  },
]

export default aiSettingsRoutes
