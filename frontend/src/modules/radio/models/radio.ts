/**
 * TypeScript models for radio recruitment system
 */

import type { Dweller } from './dweller'

export type RadioMode = 'recruitment' | 'happiness'

export interface SpeedupMultiplier {
  room_id: string
  speedup: number
}

export interface RadioStats {
  has_radio: boolean
  recruitment_rate: number // Per minute
  rate_per_hour: number
  estimated_hours_per_recruit: number
  radio_rooms_count: number
  manual_cost_caps: number
  radio_mode: RadioMode
  speedup_multipliers: SpeedupMultiplier[]
}

export interface ManualRecruitRequest {
  override?: {
    first_name?: string
    last_name?: string
    gender?: 'male' | 'female'
    special_boost?: string
    visual_attributes?: Record<string, unknown>
  }
}

export interface RecruitmentResponse {
  dweller: Dweller
  message: string
  caps_spent?: number
}
