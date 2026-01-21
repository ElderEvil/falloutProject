import type { RouteRecordRaw } from 'vue-router'

const ProfileView = () => import('../views/ProfileView.vue')
const SettingsView = () => import('../views/SettingsView.vue')
const PreferencesView = () => import('../views/PreferencesView.vue')

export const profileRoutes: RouteRecordRaw[] = [
  {
    path: '/profile',
    name: 'profile',
    component: ProfileView,
    meta: { requiresAuth: true, hideFromNav: true }
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
    meta: { requiresAuth: true, hideFromNav: false }
  },
  {
    path: '/preferences',
    name: 'preferences',
    component: PreferencesView,
    meta: { requiresAuth: true, hideFromNav: false }
  }
]

export default profileRoutes
