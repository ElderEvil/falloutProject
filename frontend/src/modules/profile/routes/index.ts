import type { RouteRecordRaw } from 'vue-router'

const ProfileView = () => import('../views/ProfileView.vue')
const SettingsView = () => import('../views/SettingsView.vue')
const PreferencesView = () => import('../views/PreferencesView.vue')
const ChangelogView = () => import('../views/ChangelogView.vue')

export const profileRoutes: RouteRecordRaw[] = [
  {
    path: '/profile',
    name: 'profile',
    component: ProfileView,
    meta: { requiresAuth: true, hideFromNav: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
    meta: { requiresAuth: true, hideFromNav: false },
  },
  {
    path: '/preferences',
    name: 'preferences',
    component: PreferencesView,
    meta: { requiresAuth: true, hideFromNav: false },
  },
  {
    path: '/changelog',
    name: 'Changelog',
    component: ChangelogView,
    meta: { requiresAuth: true, hideFromNav: false },
  },
]

export default profileRoutes
