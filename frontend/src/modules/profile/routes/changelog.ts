import { createRouter, createWebHistory } from 'vue-router'
import ChangelogView from '../views/ChangelogView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/changelog',
      name: 'Changelog',
      component: ChangelogView,
      meta: {
        title: 'Changelog',
        requiresAuth: true
      }
    }
  ]
})

export default router