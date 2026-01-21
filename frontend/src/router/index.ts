import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/modules/auth/stores/auth';

// Module routes
import { authRoutes } from '@/modules/auth/routes';
import { vaultRoutes } from '@/modules/vault/routes';
import { radioRoutes } from '@/modules/radio/routes';
import { profileRoutes } from '@/modules/profile/routes';
import { chatRoutes } from '@/modules/chat/routes';

// Lazy load all other views for code splitting
const DwellersView = () => import('@/views/DwellersView.vue');
const DwellerDetailView = () => import('@/views/DwellerDetailView.vue');

const ExplorationView = () => import('@/views/ExplorationView.vue');
const ExplorationDetailView = () => import('@/views/ExplorationDetailView.vue');
const ObjectivesView = () => import('@/views/ObjectivesView.vue');
const QuestsView = () => import('@/views/QuestsView.vue');
const RelationshipsView = () => import('@/views/RelationshipsView.vue');
const TrainingView = () => import('@/views/TrainingView.vue');



const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Vault module routes (includes home, vault, happiness)
    ...vaultRoutes,
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
    // Profile module routes
    ...profileRoutes,
    // Auth module routes
    ...authRoutes,
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
