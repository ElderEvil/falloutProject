import { apiGet } from '@/core/plugins/httpClient'
import type { AIUsageStats } from '../models/aiUsage'

export async function fetchAIUsage(): Promise<AIUsageStats> {
  return apiGet<AIUsageStats>('/api/v1/users/me/profile/ai-usage')
}
