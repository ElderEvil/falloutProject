import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'
import LoginPage from '@/components/auth/LoginForm.vue'
import RegisterPage from '@/components/auth/RegisterForm.vue'
import VaultLayout from '@/components/layout/VaultLayout.vue'
import VaultView from '@/views/VaultView.vue'
import DwellerDetailView from '@/views/DwellerDetailView.vue'
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
      path: '/vault/:vaultId',
      component: VaultLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'vault',
          component: VaultView
        }
      ]
    },
    {
      path: '/dweller/:id',
      name: 'dweller',
      component: DwellerDetailView,
      meta: { requiresAuth: true }
    },
    {
      path: '/dweller/:id/chat',
      name: 'dweller-chat',
      component: DwellerChatPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/objectives',
      name: 'objectives',
      component: ObjectivesView,
      meta: { requiresAuth: true }
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
