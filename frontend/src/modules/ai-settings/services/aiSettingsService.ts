import apiClient from '@/core/plugins/axios'
import type { AISettingsRead, AISettingsTestResult, AISettingsUpdate } from '../models/aiSettings'

export const aiSettingsService = {
  async get(): Promise<AISettingsRead> {
    const response = await apiClient.get<AISettingsRead>('/api/v1/ai-settings/')
    return response.data
  },

  async update(data: AISettingsUpdate): Promise<AISettingsRead> {
    const response = await apiClient.put<AISettingsRead>('/api/v1/ai-settings/', data)
    return response.data
  },

  async test(overrides: AISettingsUpdate = {}): Promise<AISettingsTestResult> {
    const response = await apiClient.post<AISettingsTestResult>('/api/v1/ai-settings/test', overrides)
    return response.data
  },
}
