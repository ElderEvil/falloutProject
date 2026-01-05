import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import HappinessView from './HappinessView.vue';
import { useVaultStore } from '@/stores/vault';
import { useDwellerStore } from '@/stores/dweller';
import { useIncidentStore } from '@/stores/incident';
import { useAuthStore } from '@/stores/auth';
import { createPinia, setActivePinia } from 'pinia';

// Mock stores
vi.mock('@/stores/vault');
vi.mock('@/stores/dweller');
vi.mock('@/stores/incident');
vi.mock('@/stores/auth');

// Mock composables
vi.mock('@/composables/useSidePanel', () => ({
  useSidePanel: () => ({
    isCollapsed: { value: false },
  }),
}));

describe('HappinessView', () => {
  let router: any;
  let pinia: any;

  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/happiness', name: 'happiness', component: HappinessView },
        { path: '/vault/:id/dwellers', name: 'dwellers', component: { template: '<div>Dwellers</div>' } },
        { path: '/vault/:id/radio', name: 'radio', component: { template: '<div>Radio</div>' } },
      ],
    });

    // Setup default mock implementations
    const mockVaultStore = useVaultStore();
    mockVaultStore.loadedVaults = {
      'vault-123': {
        id: 'vault-123',
        name: 'Test Vault',
        happiness: 75,
        dweller_count: 10,
        power: 80,
        power_max: 100,
        food: 70,
        food_max: 100,
        water: 90,
        water_max: 100,
        radio_mode: 'happiness',
      },
    };
    mockVaultStore.refreshVault = vi.fn().mockResolvedValue(undefined);

    const mockDwellerStore = useDwellerStore();
    mockDwellerStore.dwellers = [
      { id: '1', happiness: 90, status: 'working' },
      { id: '2', happiness: 80, status: 'working' },
      { id: '3', happiness: 60, status: 'idle' },
      { id: '4', happiness: 40, status: 'working' },
      { id: '5', happiness: 20, status: 'idle' },
    ];
    mockDwellerStore.fetchDwellers = vi.fn().mockResolvedValue(undefined);

    const mockIncidentStore = useIncidentStore();
    mockIncidentStore.activeIncidents = [
      { id: 'inc-1', type: 'raiders', is_active: true },
      { id: 'inc-2', type: 'fire', is_active: true },
    ];
    mockIncidentStore.fetchIncidents = vi.fn().mockResolvedValue(undefined);

    const mockAuthStore = useAuthStore();
    mockAuthStore.token = 'mock-token';

    vi.clearAllMocks();
  });

  it('should render loading state initially', () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Loading happiness data...');
  });

  it('should load vault, dwellers, and incidents data on mount', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    const vaultStore = useVaultStore();
    const dwellerStore = useDwellerStore();
    const incidentStore = useIncidentStore();

    expect(vaultStore.refreshVault).toHaveBeenCalledWith('vault-123', 'mock-token');
    expect(dwellerStore.fetchDwellers).toHaveBeenCalledWith('vault-123');
    expect(incidentStore.fetchIncidents).toHaveBeenCalledWith('vault-123');
  });

  it('should render dashboard after data loads', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: {
            template: '<div class="mock-dashboard">Dashboard</div>',
            props: ['vaultHappiness', 'dwellerCount', 'distribution'],
          },
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.mock-dashboard').exists()).toBe(true);
  });

  it('should pass correct props to HappinessDashboard', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: {
            template: '<div>Dashboard</div>',
            props: [
              'vaultHappiness',
              'dwellerCount',
              'distribution',
              'idleDwellerCount',
              'activeIncidentCount',
              'lowResourceCount',
              'radioHappinessMode',
            ],
          },
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    expect(dashboard.props('vaultHappiness')).toBe(75);
    expect(dashboard.props('dwellerCount')).toBe(10);
    expect(dashboard.props('idleDwellerCount')).toBe(2); // 2 idle dwellers
    expect(dashboard.props('activeIncidentCount')).toBe(2); // 2 incidents
    expect(dashboard.props('radioHappinessMode')).toBe(true);
  });

  it('should calculate dweller distribution correctly', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: {
            template: '<div>Dashboard</div>',
            props: ['distribution'],
          },
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    const distribution = dashboard.props('distribution');

    expect(distribution.high).toBe(2); // 90, 80
    expect(distribution.medium).toBe(1); // 60
    expect(distribution.low).toBe(1); // 40
    expect(distribution.critical).toBe(1); // 20
  });

  it('should calculate low resource count', async () => {
    const mockVaultStore = useVaultStore();
    mockVaultStore.loadedVaults = {
      'vault-123': {
        id: 'vault-123',
        happiness: 50,
        dweller_count: 5,
        power: 20, // 20/100 = 0.2 < 0.3 (low)
        power_max: 100,
        food: 25, // 25/100 = 0.25 < 0.3 (low)
        food_max: 100,
        water: 90, // 90/100 = 0.9 > 0.3 (ok)
        water_max: 100,
      },
    };

    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: {
            template: '<div>Dashboard</div>',
            props: ['lowResourceCount'],
          },
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    expect(dashboard.props('lowResourceCount')).toBe(2); // power and food are low
  });

  it('should handle assign-idle event and navigate to dwellers', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    await dashboard.vm.$emit('assign-idle');

    await flushPromises();

    expect(router.currentRoute.value.path).toBe('/vault/vault-123/dwellers');
    expect(router.currentRoute.value.query.filter).toBe('idle');
  });

  it('should handle activate-radio event and navigate to radio', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    await dashboard.vm.$emit('activate-radio');

    await flushPromises();

    expect(router.currentRoute.value.path).toBe('/vault/vault-123/radio');
  });

  it('should handle view-low-happiness event and navigate to dwellers', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    const dashboard = wrapper.findComponent({ name: 'HappinessDashboard' });
    await dashboard.vm.$emit('view-low-happiness');

    await flushPromises();

    expect(router.currentRoute.value.path).toBe('/vault/vault-123/dwellers');
    expect(router.currentRoute.value.query.filter).toBe('low-happiness');
  });

  it('should show error state when vault loading fails', async () => {
    const mockVaultStore = useVaultStore();
    mockVaultStore.refreshVault = vi.fn().mockRejectedValue(new Error('Failed to load'));

    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Error Loading Data');
    expect(wrapper.text()).toContain('Failed to load vault happiness data');
  });

  it('should allow retry after error', async () => {
    const mockVaultStore = useVaultStore();
    mockVaultStore.refreshVault = vi.fn().mockRejectedValue(new Error('Failed to load'));

    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    const retryButton = wrapper.find('button:has-text("Retry")');
    expect(retryButton.exists()).toBe(true);

    mockVaultStore.refreshVault = vi.fn().mockResolvedValue(undefined);
    await retryButton.trigger('click');

    await flushPromises();

    expect(mockVaultStore.refreshVault).toHaveBeenCalledTimes(1);
  });

  it('should show error when no vault ID or token', async () => {
    const mockAuthStore = useAuthStore();
    mockAuthStore.token = null;

    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Error Loading Data');
  });

  it('should render page title', async () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: true,
          HappinessDashboard: true,
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('VAULT HAPPINESS');
  });

  it('should render SidePanel', () => {
    router.push('/vault/vault-123/happiness');

    const wrapper = mount(HappinessView, {
      global: {
        plugins: [router, pinia],
        stubs: {
          SidePanel: { template: '<div class="side-panel">Panel</div>' },
          HappinessDashboard: true,
        },
      },
    });

    expect(wrapper.find('.side-panel').exists()).toBe(true);
  });
});
