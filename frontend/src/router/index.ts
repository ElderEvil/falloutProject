import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/modules/auth/stores/auth';

// Module routes
import { authRoutes } from '@/modules/auth/routes';
import { vaultRoutes } from '@/modules/vault/routes';
import { radioRoutes } from '@/modules/radio/routes';
import { profileRoutes } from '@/modules/profile/routes';
import { chatRoutes } from '@/modules/chat/routes';
import { explorationRoutes } from '@/modules/exploration/routes';
import { progressionRoutes } from '@/modules/progression/routes';
import { socialRoutes } from '@/modules/social/routes';

// Lazy load dweller views (will be moved to module in Phase 5)
const DwellersView = () => import('@/views/DwellersView.vue');
const DwellerDetailView = () => import('@/views/DwellerDetailView.vue');



const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Vault module routes (includes home, vault, happiness)
    ...vaultRoutes,
    // Dweller routes (will be moved to module in Phase 5)
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
    // Exploration module routes
    ...explorationRoutes,
    // Progression module routes (training, quests, objectives)
    ...progressionRoutes,
    // Radio module routes
    ...radioRoutes,
    // Social module routes (relationships)
    ...socialRoutes,
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
