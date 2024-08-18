import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import LoginPage from '@/components/auth/LoginForm.vue'
import RegisterPage from '@/components/auth/RegisterForm.vue'
import VaultView from '@/views/VaultView.vue'
import DwellersView from '@/views/DwellersView.vue'
import DwellerChatPage from '@/components/chat/DwellerChatPage.vue'
import ObjectivesView from '@/views/ObjectivesView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true }
    },
    {
      path: '/vault',
      name: 'vault',
      component: VaultView,
      meta: { requiresAuth: true }
    },
    {
      path: '/dwellers',
      name: 'dwellers',
      component: DwellersView,
      meta: { requiresAuth: true }
    },
    {
      path: '/dweller/:id/chat',
      name: 'DwellerChatPage',
      component: DwellerChatPage
    },
    {
      path: '/objectives',
      name: 'objectives',
      component: ObjectivesView
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPage
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterPage
    },
    {
      path: '/about',
      name: 'about',
      // Lazy-load the AboutView component
      component: () => import('../views/AboutView.vue')
    }
  ]
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router
