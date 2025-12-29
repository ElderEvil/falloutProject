import { defineStore } from 'pinia';
import axios from '@/plugins/axios';

export interface ExplorationEvent {
  type: string;
  description: string;
  timestamp: string;
  time_elapsed_hours: number;
  loot?: {
    item: {
      name: string
      rarity: string
      value: number
    }
    caps: number
  };
}

export interface LootItem {
  item_name: string;
  quantity: number;
  rarity: string;
  found_at: string;
}

export interface Exploration {
  id: string;
  vault_id: string;
  dweller_id: string;
  status: 'active' | 'completed' | 'recalled';
  duration: number;
  start_time: string;
  end_time: string | null;
  events: ExplorationEvent[];
  loot_collected: LootItem[];
  total_distance: number;
  total_caps_found: number;
  enemies_encountered: number;
  created_at: string;
  updated_at: string;
  dweller_strength: number;
  dweller_perception: number;
  dweller_endurance: number;
  dweller_charisma: number;
  dweller_intelligence: number;
  dweller_agility: number;
  dweller_luck: number;
}

export interface ExplorationProgress {
  id: string;
  status: 'ACTIVE' | 'COMPLETED' | 'RECALLED';
  progress_percentage: number;
  time_remaining_seconds: number;
  elapsed_time_seconds: number;
  events: ExplorationEvent[];
  loot_collected: LootItem[];
}

export interface RewardsSummary {
  caps: number;
  items: LootItem[];
  experience: number;
  distance: number;
  enemies_defeated: number;
  events_encountered: number;
  progress_percentage?: number;
  recalled_early?: boolean;
}

export const useExplorationStore = defineStore('exploration', {
  state: () => ({
    explorations: [] as Exploration[],
    activeExplorations: {} as Record<string, Exploration>,
    lastRewards: null as RewardsSummary | null,
    isLoading: false,
    error: null as string | null
  }),

  getters: {
    getExplorationByDwellerId: (state) => (dwellerId: string) => {
      return state.explorations.find((e) => e.dweller_id === dwellerId && e.status === 'active');
    },

    getActiveExplorationsForVault: (state) => (vaultId: string) => {
      return state.explorations.filter((e) => e.vault_id === vaultId && e.status === 'active');
    },

    isDwellerExploring: (state) => (dwellerId: string) => {
      return state.explorations.some((e) => e.dweller_id === dwellerId && e.status === 'active');
    }
  },

  actions: {
    async sendDwellerToWasteland(
      vaultId: string,
      dwellerId: string,
      duration: number,
      token: string
    ) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await axios.post(
          `/api/v1/explorations/send?vault_id=${vaultId}`,
          {
            dweller_id: dwellerId,
            duration
          },
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );

        const exploration = response.data;
        this.explorations.push(exploration);
        this.activeExplorations[exploration.id] = exploration;

        return exploration;
      } catch (error) {
        console.error('Failed to send dweller to wasteland:', error);
        this.error = 'Failed to send dweller to wasteland';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchExplorationsByVault(vaultId: string, token: string, activeOnly = true) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await axios.get(
          `/api/v1/explorations/vault/${vaultId}?active_only=${activeOnly}`,
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );

        this.explorations = response.data;
        // Update active explorations map
        this.activeExplorations = {};
        response.data
          .filter((e: Exploration) => e.status === 'active')
          .forEach((e: Exploration) => {
            this.activeExplorations[e.id] = e;
          });

        return response.data;
      } catch (error) {
        console.error('Failed to fetch explorations:', error);
        this.error = 'Failed to fetch explorations';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchExplorationDetails(explorationId: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/explorations/${explorationId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        // Update in explorations list
        const index = this.explorations.findIndex((e) => e.id === explorationId);
        if (index !== -1) {
          this.explorations[index] = response.data;
        }

        // Update in active explorations
        if (response.data.status === 'active') {
          this.activeExplorations[explorationId] = response.data;
        } else {
          delete this.activeExplorations[explorationId];
        }

        return response.data;
      } catch (error) {
        console.error('Failed to fetch exploration details:', error);
        throw error;
      }
    },

    async fetchExplorationProgress(explorationId: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/explorations/${explorationId}/progress`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        return response.data as ExplorationProgress;
      } catch (error) {
        console.error('Failed to fetch exploration progress:', error);
        throw error;
      }
    },

    async recallDweller(explorationId: string, token: string) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await axios.post(
          `/api/v1/explorations/${explorationId}/recall`,
          {},
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );

        const { exploration, rewards_summary } = response.data;
        this.lastRewards = rewards_summary;

        // Update exploration in state
        const index = this.explorations.findIndex((e) => e.id === explorationId);
        if (index !== -1) {
          this.explorations[index] = exploration;
        }

        // Remove from active explorations
        delete this.activeExplorations[explorationId];

        return response.data;
      } catch (error) {
        console.error('Failed to recall dweller:', error);
        this.error = 'Failed to recall dweller';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async completeExploration(explorationId: string, token: string) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await axios.post(
          `/api/v1/explorations/${explorationId}/complete`,
          {},
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );

        const { exploration, rewards_summary } = response.data;
        this.lastRewards = rewards_summary;

        // Update exploration in state
        const index = this.explorations.findIndex((e) => e.id === explorationId);
        if (index !== -1) {
          this.explorations[index] = exploration;
        }

        // Remove from active explorations
        delete this.activeExplorations[explorationId];

        return response.data;
      } catch (error) {
        console.error('Failed to complete exploration:', error);
        this.error = 'Failed to complete exploration';
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    clearLastRewards() {
      this.lastRewards = null;
    },

    clearError() {
      this.error = null;
    }
  }
});
