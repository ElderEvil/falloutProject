import apiClient from '@/core/plugins/axios'
import type { AISettingsRead, AISettingsUpdate } from '../models/aiSettings'

export const aiSettingsService = {
  async get(): Promise<AISettingsRead> {
    const response = await apiClient.get<AISettingsRead>('/api/v1/ai-settings')
    return response.data
  },

  async update(data: AISettingsUpdate): Promise<AISettingsRead> {
    const response = await apiClient.put<AISettingsRead>('/api/v1/ai-settings', data)
    return response.data
  },
}
