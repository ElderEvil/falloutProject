import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import HomeView from '@/views/HomeView.vue';
import LoginPage from '@/components/auth/LoginForm.vue';
import RegisterPage from '@/components/auth/RegisterForm.vue';
import VaultView from '@/views/VaultView.vue';
import DwellersView from '@/views/DwellersView.vue';
import DwellerDetailView from '@/views/DwellerDetailView.vue';
import DwellerChatPage from '@/components/chat/DwellerChatPage.vue';
import ObjectivesView from '@/views/ObjectivesView.vue';
import RadioView from '@/views/RadioView.vue';
import RelationshipsView from '@/views/RelationshipsView.vue';

import TrainingView from '@/views/TrainingView.vue';
import ProfileView from '@/views/ProfileView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true, hideFromNav: false }
    },
    {
      path: '/vault/:id',
      name: 'vault',
      component: VaultView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/dwellers',
      name: 'dwellers',
      component: DwellersView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/dwellers/:dwellerId',
      name: 'dwellerDetail',
      component: DwellerDetailView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/dweller/:id/chat',
      name: 'DwellerChatPage',
      component: DwellerChatPage
    },
    {
      path: '/vault/:id/objectives',
      name: 'objectives',
      component: ObjectivesView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/radio',
      name: 'radio',
      component: RadioView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/relationships',
      name: 'relationships',
      component: RelationshipsView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/training',
      name: 'training',
      component: TrainingView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfileView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { hideFromNav: true }
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterPage,
      meta: { hideFromNav: true }
    },
    {
      path: '/about',
      name: 'about',
      // Lazy-load the AboutView component
      component: () => import('../views/AboutView.vue')
    }
  ]
});

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login');
  } else {
    next();
  }
});

export default router;
