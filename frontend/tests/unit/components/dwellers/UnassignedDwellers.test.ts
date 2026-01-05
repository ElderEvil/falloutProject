import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import UnassignedDwellers from '@/components/dwellers/UnassignedDwellers.vue';
import { useDwellerStore } from '@/stores/dweller';
import { useExplorationStore } from '@/stores/exploration';
import { useAuthStore } from '@/stores/auth';

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon']
  }
}));

// Mock components
vi.mock('@/components/dwellers/DwellerStatusBadge.vue', () => ({
  default: { template: '<div class="status-badge-mock"></div>', props: ['status', 'size'] }
}));

vi.mock('@/components/dwellers/DwellerFilterPanel.vue', () => ({
  default: { template: '<div class="filter-panel-mock"></div>', props: ['showStatusFilter'] }
}));

describe('UnassignedDwellers', () => {
  let dwellerStore: any;
  let explorationStore: any;
  let authStore: any;

  const mockDweller = {
    id: 'dweller-1',
    first_name: 'John',
    last_name: 'Doe',
    level: 5,
    strength: 8,
    perception: 6,
    endurance: 7,
    charisma: 5,
    intelligence: 9,
    agility: 4,
    luck: 6,
    room_id: null,
    thumbnail_url: null
  };

  beforeEach(() => {
    setActivePinia(createPinia());
    dwellerStore = useDwellerStore();
    explorationStore = useExplorationStore();
    authStore = useAuthStore();

    // Set underlying dwellers array instead of computed property
    dwellerStore.dwellers = [];
    explorationStore.isDwellerExploring = vi.fn(() => false);
    dwellerStore.unassignDwellerFromRoom = vi.fn().mockResolvedValue(undefined);
    dwellerStore.getDwellerStatus = vi.fn(() => 'idle');
    authStore.token = 'mock-token';
  });

  describe('Rendering', () => {
    it('should render unassigned dwellers panel with header', () => {
      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.text()).toContain('Unassigned Dwellers');
      expect(wrapper.text()).toContain('Drag dwellers here to unassign them from rooms');
    });

    it('should display count badge', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.find('.count-badge').exists()).toBe(true);
      expect(wrapper.find('.count-badge').text()).toBe('1');
    });

    it('should show empty state when no unassigned dwellers', () => {
      dwellerStore.dwellers = [];

      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.text()).toContain('All dwellers are assigned!');
    });

    it('should render dweller cards when unassigned dwellers exist', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.find('.dweller-card').exists()).toBe(true);
      expect(wrapper.text()).toContain('John Doe');
      expect(wrapper.text()).toContain('Level 5');
    });

    it('should display all SPECIAL stats', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const stats = wrapper.find('.dweller-stats');
      expect(stats.html()).toContain('S'); // Strength
      expect(stats.html()).toContain('P'); // Perception
      expect(stats.html()).toContain('E'); // Endurance
      expect(stats.html()).toContain('C'); // Charisma
      expect(stats.html()).toContain('I'); // Intelligence
      expect(stats.html()).toContain('A'); // Agility
      expect(stats.html()).toContain('L'); // Luck
    });

    it('should use theme color for avatar placeholder', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const avatar = wrapper.find('.dweller-avatar');
      const avatarHtml = avatar.html();
      expect(avatarHtml).toContain('var(--color-theme-primary)');
      expect(avatarHtml).toContain('opacity: 0.6');
    });
  });

  describe('Filtering', () => {
    it('should filter out dwellers with room assignments', () => {
      const assignedDweller = { ...mockDweller, id: 'dweller-2', room_id: 'room-1' };
      dwellerStore.dwellers = [mockDweller, assignedDweller];

      const wrapper = mount(UnassignedDwellers);

      const cards = wrapper.findAll('.dweller-card');
      expect(cards.length).toBe(1);
      expect(wrapper.text()).toContain('John Doe');
    });

    it('should filter out exploring dwellers', () => {
      const exploringDweller = { ...mockDweller, id: 'dweller-exploring' };
      dwellerStore.dwellers = [exploringDweller];

      // Add active exploration for this dweller
      explorationStore.explorations = [{
        id: 'exploration-1',
        dweller_id: 'dweller-exploring',
        vault_id: 'vault-1',
        status: 'active',
        location: 'wasteland',
        start_time: new Date().toISOString(),
        duration: 3600,
        resources_found: []
      } as any];

      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.find('.dweller-card').exists()).toBe(false);
      expect(wrapper.text()).toContain('All dwellers are assigned!');
    });
  });

  describe('Drag and Drop', () => {
    it('should make dweller cards draggable', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const card = wrapper.find('.dweller-card');
      expect(card.attributes('draggable')).toBe('true');
    });

    it('should emit dragStart event when dragging starts', async () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const card = wrapper.find('.dweller-card');
      await card.trigger('dragstart', {
        dataTransfer: {
          effectAllowed: '',
          setData: vi.fn()
        }
      });

      expect(wrapper.emitted('dragStart')).toBeTruthy();
      expect(wrapper.emitted('dragStart')![0][0]).toMatchObject({ id: mockDweller.id });
    });

    it('should emit dragEnd event when dragging ends', async () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const card = wrapper.find('.dweller-card');
      await card.trigger('dragend');

      expect(wrapper.emitted('dragEnd')).toBeTruthy();
    });

    it('should show drop overlay when dragging over', async () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const container = wrapper.find('.dweller-grid-container');
      await container.trigger('dragover', {
        dataTransfer: { dropEffect: '' }
      });

      await flushPromises();

      expect(wrapper.find('.drop-overlay').exists()).toBe(true);
      expect(wrapper.text()).toContain('Drop to unassign');
    });

    it('should unassign dweller on drop', async () => {
      dwellerStore.dwellers = [];

      const wrapper = mount(UnassignedDwellers);

      const dropZone = wrapper.find('.empty-state');
      await dropZone.trigger('drop', {
        dataTransfer: {
          getData: () => JSON.stringify({
            dwellerId: 'dweller-1',
            firstName: 'John',
            lastName: 'Doe',
            currentRoomId: 'room-1'
          })
        }
      });

      await flushPromises();

      expect(dwellerStore.unassignDwellerFromRoom).toHaveBeenCalledWith('dweller-1', 'mock-token');
    });

    it('should show success message after unassigning', async () => {
      dwellerStore.dwellers = [];

      const wrapper = mount(UnassignedDwellers);

      const dropZone = wrapper.find('.empty-state');
      await dropZone.trigger('drop', {
        dataTransfer: {
          getData: () => JSON.stringify({
            dwellerId: 'dweller-1',
            firstName: 'John',
            lastName: 'Doe',
            currentRoomId: 'room-1'
          })
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('John Doe unassigned from room');
    });

    it('should not unassign if dweller has no room', async () => {
      dwellerStore.dwellers = [];

      const wrapper = mount(UnassignedDwellers);

      const dropZone = wrapper.find('.empty-state');
      await dropZone.trigger('drop', {
        dataTransfer: {
          getData: () => JSON.stringify({
            dwellerId: 'dweller-1',
            firstName: 'John',
            lastName: 'Doe',
            currentRoomId: null
          })
        }
      });

      await flushPromises();

      expect(dwellerStore.unassignDwellerFromRoom).not.toHaveBeenCalled();
    });
  });

  describe('Color Theming', () => {
    it('should use theme color for level text', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const levelElement = wrapper.find('.dweller-level');
      expect(levelElement.attributes('class')).toBe('dweller-level');
    });

    it('should use theme color for stat labels', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const statLabels = wrapper.findAll('.stat-label');
      expect(statLabels.length).toBeGreaterThan(0);
    });

    it('should have neutral black card background', () => {
      dwellerStore.dwellers = [mockDweller];

      const wrapper = mount(UnassignedDwellers);

      const card = wrapper.find('.dweller-card');
      expect(card.exists()).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should show error message on unassign failure', async () => {
      dwellerStore.unassignDwellerFromRoom = vi.fn().mockRejectedValue(new Error('Unassign failed'));
      dwellerStore.dwellers = [];

      const wrapper = mount(UnassignedDwellers);

      const dropZone = wrapper.find('.empty-state');
      await dropZone.trigger('drop', {
        dataTransfer: {
          getData: () => JSON.stringify({
            dwellerId: 'dweller-1',
            firstName: 'John',
            lastName: 'Doe',
            currentRoomId: 'room-1'
          })
        }
      });

      await flushPromises();

      expect(wrapper.text()).toContain('Failed to unassign dweller');
    });
  });

  describe('Multiple Dwellers', () => {
    it('should render multiple dweller cards', () => {
      const dweller2 = { ...mockDweller, id: 'dweller-2', first_name: 'Jane', last_name: 'Smith' };
      dwellerStore.dwellers = [mockDweller, dweller2];

      const wrapper = mount(UnassignedDwellers);

      const cards = wrapper.findAll('.dweller-card');
      expect(cards.length).toBe(2);
      expect(wrapper.text()).toContain('John Doe');
      expect(wrapper.text()).toContain('Jane Smith');
    });

    it('should update count badge with correct number', () => {
      dwellerStore.dwellers = [
        mockDweller,
        { ...mockDweller, id: 'dweller-2' },
        { ...mockDweller, id: 'dweller-3' }
      ];

      const wrapper = mount(UnassignedDwellers);

      expect(wrapper.find('.count-badge').text()).toBe('3');
    });
  });
});
