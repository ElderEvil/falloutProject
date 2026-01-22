import { describe, it, expect, vi, beforeEach } from 'vitest';
import { happinessService } from '@/services/happinessService';
import type { AxiosResponse } from 'axios';
import apiClient from '@/core/plugins/axios';

vi.mock('@/core/plugins/axios');

describe('happinessService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getDwellerModifiers', () => {
    it('should fetch happiness modifiers for a dweller', async () => {
      const mockResponse: AxiosResponse = {
        data: {
          current_happiness: 75,
          positive: [
            { name: 'Working', value: 2.0 },
            { name: 'High Health', value: 1.0 },
          ],
          negative: [
            { name: 'Base Decay', value: -0.5 },
          ],
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {} as any,
      };

      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      const result = await happinessService.getDwellerModifiers('dweller-123');

      expect(apiClient.get).toHaveBeenCalledWith('api/v1/dwellers/dweller-123/happiness_modifiers');
      expect(result.data.current_happiness).toBe(75);
      expect(result.data.positive).toHaveLength(2);
      expect(result.data.negative).toHaveLength(1);
    });

    it('should handle API errors', async () => {
      vi.mocked(apiClient.get).mockRejectedValue(new Error('API Error'));

      await expect(
        happinessService.getDwellerModifiers('dweller-123')
      ).rejects.toThrow('API Error');
    });
  });

  describe('calculateDistribution', () => {
    it('should calculate correct distribution for dwellers', () => {
      const dwellers = [
        { happiness: 90 }, // high
        { happiness: 80 }, // high
        { happiness: 75 }, // high (boundary)
        { happiness: 65 }, // medium
        { happiness: 50 }, // medium (boundary)
        { happiness: 40 }, // low
        { happiness: 25 }, // low (boundary)
        { happiness: 15 }, // critical
        { happiness: 10 }, // critical (boundary)
      ];

      const result = happinessService.calculateDistribution(dwellers);

      expect(result.high).toBe(3);
      expect(result.medium).toBe(2);
      expect(result.low).toBe(2);
      expect(result.critical).toBe(2);
    });

    it('should handle empty dweller array', () => {
      const result = happinessService.calculateDistribution([]);

      expect(result.high).toBe(0);
      expect(result.medium).toBe(0);
      expect(result.low).toBe(0);
      expect(result.critical).toBe(0);
    });

    it('should handle dwellers with missing happiness values', () => {
      const dwellers = [
        { happiness: 0 },
        {},
        { happiness: undefined },
      ] as any;

      const result = happinessService.calculateDistribution(dwellers);

      // Note: happiness: 0 is treated as falsy and defaults to 50 (medium)
      // All three cases default to 50 (medium)
      expect(result.critical).toBe(0);
      expect(result.medium).toBe(3); // all values default to 50
    });

    it('should handle all dwellers in one category', () => {
      const dwellers = [
        { happiness: 100 },
        { happiness: 95 },
        { happiness: 85 },
        { happiness: 75 },
      ];

      const result = happinessService.calculateDistribution(dwellers);

      expect(result.high).toBe(4);
      expect(result.medium).toBe(0);
      expect(result.low).toBe(0);
      expect(result.critical).toBe(0);
    });
  });

  describe('getHappinessLevel', () => {
    it('should return "high" for happiness >= 75', () => {
      expect(happinessService.getHappinessLevel(100)).toBe('high');
      expect(happinessService.getHappinessLevel(75)).toBe('high');
      expect(happinessService.getHappinessLevel(80)).toBe('high');
    });

    it('should return "medium" for happiness 50-74', () => {
      expect(happinessService.getHappinessLevel(74)).toBe('medium');
      expect(happinessService.getHappinessLevel(50)).toBe('medium');
      expect(happinessService.getHappinessLevel(60)).toBe('medium');
    });

    it('should return "low" for happiness 25-49', () => {
      expect(happinessService.getHappinessLevel(49)).toBe('low');
      expect(happinessService.getHappinessLevel(25)).toBe('low');
      expect(happinessService.getHappinessLevel(35)).toBe('low');
    });

    it('should return "critical" for happiness < 25', () => {
      expect(happinessService.getHappinessLevel(24)).toBe('critical');
      expect(happinessService.getHappinessLevel(10)).toBe('critical');
      expect(happinessService.getHappinessLevel(0)).toBe('critical');
    });
  });

  describe('getHappinessColor', () => {
    it('should return correct colors for each level', () => {
      expect(happinessService.getHappinessColor(100)).toBe('var(--color-theme-primary)');
      expect(happinessService.getHappinessColor(75)).toBe('var(--color-theme-primary)');

      expect(happinessService.getHappinessColor(60)).toBe('#4ade80');
      expect(happinessService.getHappinessColor(50)).toBe('#4ade80');

      expect(happinessService.getHappinessColor(35)).toBe('#fbbf24');
      expect(happinessService.getHappinessColor(25)).toBe('#fbbf24');

      expect(happinessService.getHappinessColor(20)).toBe('#ef4444');
      expect(happinessService.getHappinessColor(0)).toBe('#ef4444');
    });

    it('should handle boundary values correctly', () => {
      expect(happinessService.getHappinessColor(75)).toBe('var(--color-theme-primary)'); // high
      expect(happinessService.getHappinessColor(74)).toBe('#4ade80'); // medium
      expect(happinessService.getHappinessColor(50)).toBe('#4ade80'); // medium
      expect(happinessService.getHappinessColor(49)).toBe('#fbbf24'); // low
      expect(happinessService.getHappinessColor(25)).toBe('#fbbf24'); // low
      expect(happinessService.getHappinessColor(24)).toBe('#ef4444'); // critical
    });
  });
});
