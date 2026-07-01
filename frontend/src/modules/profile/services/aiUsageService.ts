import axios from '@/core/plugins/axios'
import type { AIUsageStats } from '../models/aiUsage'

export async function fetchAIUsage(): Promise<AIUsageStats> {
  const response = await axios.get<AIUsageStats>('/api/v1/users/me/profile/ai-usage')
  return response.data
}
