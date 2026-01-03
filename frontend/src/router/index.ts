import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// Eager load only the home view for fastest initial load
import HomeView from '@/views/HomeView.vue';

// Lazy load all other views for code splitting
const LoginPage = () => import('@/components/auth/LoginForm.vue');
const RegisterPage = () => import('@/components/auth/RegisterForm.vue');
const VaultView = () => import('@/views/VaultView.vue');
const DwellersView = () => import('@/views/DwellersView.vue');
const DwellerDetailView = () => import('@/views/DwellerDetailView.vue');
const DwellerChatPage = () => import('@/components/chat/DwellerChatPage.vue');
const ObjectivesView = () => import('@/views/ObjectivesView.vue');
const QuestsView = () => import('@/views/QuestsView.vue');
const RadioView = () => import('@/views/RadioView.vue');
const RelationshipsView = () => import('@/views/RelationshipsView.vue');
const TrainingView = () => import('@/views/TrainingView.vue');
const ProfileView = () => import('@/views/ProfileView.vue');

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
      path: '/vault/:id/quests',
      name: 'quests',
      component: QuestsView,
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
