import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import RelationshipsView from '@/modules/social/views/RelationshipsView.vue';
import { useRelationshipStore } from '@/modules/social/stores/relationship';
import { useDwellerStore } from '@/modules/dwellers/stores/dweller';
import { useAuthStore } from '@/modules/auth/stores/auth';

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon']
  }
}));

// Mock UButton
vi.mock('@/core/components/ui/UButton.vue', () => ({
  default: {
    name: 'UButton',
    template: '<button class="u-button-mock" @click="$emit(\'click\')"><slot /></button>',
    props: ['variant', 'size', 'disabled']
  }
}));

// Mock the components
vi.mock('@/core/components/common/SidePanel.vue', () => ({
  default: { template: '<div class="side-panel-mock"></div>' }
}));

vi.mock('@/modules/social/components/relationships/RelationshipList.vue', () => ({
  default: { template: '<div class="relationship-list-mock"></div>', props: ['vaultId', 'stageFilter'] }
}));

vi.mock('@/modules/social/components/pregnancy/PregnancyTracker.vue', () => ({
  default: { template: '<div class="pregnancy-tracker-mock"></div>', props: ['vaultId', 'autoRefresh'] }
}));

vi.mock('@/modules/social/components/relationships/ChildrenList.vue', () => ({
  default: { template: '<div class="children-list-mock"></div>', props: ['vaultId'] }
}));

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } })
}));

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn()
  })
}));

describe('RelationshipsView', () => {
  let router: any;
  let relationshipStore: any;
  let dwellerStore: any;
  let authStore: any;

  beforeEach(() => {
    setActivePinia(createPinia());
    relationshipStore = useRelationshipStore();
    dwellerStore = useDwellerStore();
    authStore = useAuthStore();

    // Mock store methods
    vi.spyOn(relationshipStore, 'fetchVaultRelationships').mockResolvedValue(undefined);
    vi.spyOn(relationshipStore, 'fetchVaultPregnancies').mockResolvedValue(undefined);
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue(undefined);
    vi.spyOn(relationshipStore, 'quickPair').mockResolvedValue(true);
    vi.spyOn(relationshipStore, 'processVaultBreeding').mockResolvedValue({
      stats: { relationships_updated: 0, conceptions: 0, births: 0, children_aged: 0 }
    });

    // Set up mock data
    relationshipStore.relationships = [];
    relationshipStore.pregnancies = [];
    relationshipStore.token = 'mock-token';
    dwellerStore.dwellers = [];
    authStore.user = { is_superuser: false } as any;

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/vault/:id/relationships',
          component: RelationshipsView,
          name: 'relationships'
        }
      ]
    });

    router.push('/vault/test-vault-id/relationships');
  });

  describe('Rendering', () => {
    it('should render relationships view with header', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Relationships & Family');
    });

    it('should render all four tabs', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Forming');
      expect(wrapper.text()).toContain('Partners');
      expect(wrapper.text()).toContain('Pregnancies');
      expect(wrapper.text()).toContain('Children');
    });

    it('should render stats overview cards', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Total Relationships');
      expect(wrapper.text()).toContain('Partner Couples');
      expect(wrapper.text()).toContain('Active Pregnancies');
      expect(wrapper.text()).toContain('Growing Children');
    });

    it('should render action buttons for superuser', async () => {
      authStore.user = { is_superuser: true } as any;

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Vault-Tec Matchmaker');
      expect(wrapper.text()).toContain('Process Now');
    });

    it('should not render action buttons for non-superuser', async () => {
      authStore.user = { is_superuser: false } as any;

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(wrapper.text()).not.toContain('Vault-Tec Matchmaker');
      expect(wrapper.text()).not.toContain('Process Now');
    });

    it('should have terminal-style tab styling', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const tabs = wrapper.findAll('.stage-tab');
      expect(tabs.length).toBe(4);

      // Check that first tab is active by default
      expect(tabs[0].classes()).toContain('active');
    });
  });

  describe('Tab Switching', () => {
    it('should switch to partners tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const tabs = wrapper.findAll('.stage-tab');
      await tabs[1].trigger('click');

      await flushPromises();

      expect(tabs[1].classes()).toContain('active');
      expect(wrapper.text()).toContain('Partner Couples');
    });

    it('should switch to pregnancies tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const tabs = wrapper.findAll('.stage-tab');
      await tabs[2].trigger('click');

      await flushPromises();

      expect(tabs[2].classes()).toContain('active');
      expect(wrapper.text()).toContain('Active Pregnancies');
    });

    it('should switch to children tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const tabs = wrapper.findAll('.stage-tab');
      await tabs[3].trigger('click');

      await flushPromises();

      expect(tabs[3].classes()).toContain('active');
      expect(wrapper.text()).toContain('Growing Children');
    });

    it('should display correct content for each tab', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      // Forming tab (default)
      expect(wrapper.text()).toContain('Forming Relationships');

      // Switch to partners
      const tabs = wrapper.findAll('.stage-tab');
      await tabs[1].trigger('click');
      await flushPromises();
      expect(wrapper.text()).toContain('Committed partners in living quarters');
    });
  });

  describe('Quick Pair Functionality', () => {
    it('should call quickPair when button is clicked', async () => {
      authStore.user = { is_superuser: true } as any;
      await router.isReady();

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const matchmakerButton = wrapper.findAll('.u-button-mock').find(btn =>
        btn.text().includes('Vault-Tec Matchmaker')
      );

      expect(matchmakerButton).toBeDefined();
      await matchmakerButton!.trigger('click');

      await flushPromises();

      expect(relationshipStore.quickPair).toHaveBeenCalledWith('test-vault-id');
    });

    it('should refresh relationships after quick pair', async () => {
      authStore.user = { is_superuser: true } as any;
      await router.isReady();

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const matchmakerButton = wrapper.findAll('.u-button-mock').find(btn =>
        btn.text().includes('Vault-Tec Matchmaker')
      );

      await matchmakerButton!.trigger('click');
      await flushPromises();

      expect(relationshipStore.fetchVaultRelationships).toHaveBeenCalled();
    });
  });

  describe('Process Breeding Functionality', () => {
    it('should call processVaultBreeding when button is clicked', async () => {
      authStore.user = { is_superuser: true } as any;
      await router.isReady();

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const processButton = wrapper.findAll('.u-button-mock').find(btn =>
        btn.text().includes('Process Now')
      );

      expect(processButton).toBeDefined();
      await processButton!.trigger('click');

      await flushPromises();

      expect(relationshipStore.processVaultBreeding).toHaveBeenCalledWith('test-vault-id');
    });

    it('should refresh all data after processing', async () => {
      authStore.user = { is_superuser: true } as any;
      await router.isReady();

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const processButton = wrapper.findAll('.u-button-mock').find(btn =>
        btn.text().includes('Process Now')
      );

      await processButton!.trigger('click');
      await flushPromises();

      expect(relationshipStore.fetchVaultRelationships).toHaveBeenCalled();
      expect(relationshipStore.fetchVaultPregnancies).toHaveBeenCalled();
      expect(dwellerStore.fetchDwellersByVault).toHaveBeenCalled();
    });
  });

  describe('Stats Display', () => {
    it('should display correct relationship count', async () => {
      relationshipStore.relationships = [
        { id: '1', relationship_type: 'friend' },
        { id: '2', relationship_type: 'partner' }
      ];

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const stats = wrapper.findAll('.stat-value');
      expect(stats[0].text()).toBe('2'); // Total relationships
    });

    it('should display correct partner count', async () => {
      relationshipStore.relationships = [
        { id: '1', relationship_type: 'friend' },
        { id: '2', relationship_type: 'partner' },
        { id: '3', relationship_type: 'partner' }
      ];

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const stats = wrapper.findAll('.stat-value');
      expect(stats[1].text()).toBe('2'); // Partner couples
    });

    it('should display correct pregnancy count', async () => {
      relationshipStore.pregnancies = [
        { id: '1' },
        { id: '2' }
      ];

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const stats = wrapper.findAll('.stat-value');
      expect(stats[2].text()).toBe('2'); // Active pregnancies
    });

    it('should display correct children count', async () => {
      dwellerStore.dwellers = [
        { id: '1', age_group: 'child' },
        { id: '2', age_group: 'adult' },
        { id: '3', age_group: 'child' }
      ];

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      const stats = wrapper.findAll('.stat-value');
      expect(stats[3].text()).toBe('2'); // Growing children
    });
  });

  describe('Data Loading', () => {
    it('should fetch all data on mount', async () => {
      await router.isReady();

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router]
        }
      });

      await flushPromises();

      expect(relationshipStore.fetchVaultRelationships).toHaveBeenCalledWith('test-vault-id');
      expect(relationshipStore.fetchVaultPregnancies).toHaveBeenCalledWith('test-vault-id');
      expect(dwellerStore.fetchDwellersByVault).toHaveBeenCalledWith('test-vault-id', 'mock-token');
    });
  });
});
