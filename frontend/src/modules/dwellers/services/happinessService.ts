import apiClient from '@/core/plugins/axios'
import type { AxiosResponse } from 'axios'

export interface HappinessModifier {
  name: string
  value: number
}

export interface HappinessModifiers {
  current_happiness: number
  positive: HappinessModifier[]
  negative: HappinessModifier[]
}

export interface DwellerHappinessDistribution {
  high: number // 75-100
  medium: number // 50-74
  low: number // 25-49
  critical: number // 10-24
}

export const happinessService = {
  /**
   * Get detailed happiness modifiers for a specific dweller
   */
  async getDwellerModifiers(dwellerId: string): Promise<AxiosResponse<HappinessModifiers>> {
    return await apiClient.get(`api/v1/dwellers/${dwellerId}/happiness_modifiers`)
  },

  /**
   * Calculate happiness distribution from dwellers array
   */
  calculateDistribution(dwellers: Array<{ happiness: number }>): DwellerHappinessDistribution {
    const distribution: DwellerHappinessDistribution = {
      high: 0,
      medium: 0,
      low: 0,
      critical: 0,
    }

    dwellers.forEach((dweller) => {
      const happiness = dweller.happiness || 50
      if (happiness >= 75) {
        distribution.high++
      } else if (happiness >= 50) {
        distribution.medium++
      } else if (happiness >= 25) {
        distribution.low++
      } else {
        distribution.critical++
      }
    })

    return distribution
  },

  /**
   * Get happiness level category
   */
  getHappinessLevel(happiness: number): 'high' | 'medium' | 'low' | 'critical' {
    if (happiness >= 75) return 'high'
    if (happiness >= 50) return 'medium'
    if (happiness >= 25) return 'low'
    return 'critical'
  },

  /**
   * Get color for happiness level
   */
  getHappinessColor(happiness: number): string {
    const level = this.getHappinessLevel(happiness)
    switch (level) {
      case 'high':
        return 'var(--color-theme-primary)'
      case 'medium':
        return '#4ade80'
      case 'low':
        return '#fbbf24'
      case 'critical':
        return '#ef4444'
      default:
        return 'var(--color-theme-primary)'
    }
  },
}
