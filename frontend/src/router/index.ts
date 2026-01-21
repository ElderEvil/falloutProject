import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// Module routes
import { radioRoutes } from '@/modules/radio/routes';
import { profileRoutes } from '@/modules/profile/routes';
import { chatRoutes } from '@/modules/chat/routes';

// Eager load only the home view for fastest initial load
import HomeView from '@/views/HomeView.vue';

// Lazy load all other views for code splitting
const LoginPage = () => import('@/components/auth/LoginFormTerminal.vue');
const RegisterPage = () => import('@/components/auth/RegisterForm.vue');
const VaultView = () => import('@/views/VaultView.vue');
const DwellersView = () => import('@/views/DwellersView.vue');
const DwellerDetailView = () => import('@/views/DwellerDetailView.vue');

const ExplorationView = () => import('@/views/ExplorationView.vue');
const ExplorationDetailView = () => import('@/views/ExplorationDetailView.vue');
const ObjectivesView = () => import('@/views/ObjectivesView.vue');
const QuestsView = () => import('@/views/QuestsView.vue');
const RelationshipsView = () => import('@/views/RelationshipsView.vue');
const TrainingView = () => import('@/views/TrainingView.vue');
const HappinessView = () => import('@/views/HappinessView.vue');

const ResetPasswordView = () => import('@/views/ResetPasswordView.vue');
const ForgotPasswordView = () => import('@/views/ForgotPasswordView.vue');
const VerifyEmailView = () => import('@/views/VerifyEmailView.vue');

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
    // Chat module routes
    ...chatRoutes,
    {
      path: '/vault/:id/exploration',
      name: 'exploration',
      component: ExplorationView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    {
      path: '/vault/:id/exploration/:explorationId',
      name: 'explorationDetail',
      component: ExplorationDetailView,
      meta: { requiresAuth: true, hideFromNav: true }
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
    // Radio module routes
    ...radioRoutes,
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
      path: '/vault/:id/happiness',
      name: 'happiness',
      component: HappinessView,
      meta: { requiresAuth: true, hideFromNav: true }
    },
    // Profile module routes
    ...profileRoutes,
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
      path: '/forgot-password',
      name: 'forgot-password',
      component: ForgotPasswordView,
      meta: { hideFromNav: true }
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: ResetPasswordView,
      meta: { hideFromNav: true }
    },
    {
      path: '/verify-email',
      name: 'verify-email',
      component: VerifyEmailView,
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
