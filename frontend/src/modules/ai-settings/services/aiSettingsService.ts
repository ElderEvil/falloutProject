import { apiGet, apiPost, apiPut } from '@/core/utils/api'
import type { AISettingsRead, AISettingsTestResult, AISettingsUpdate } from '../models/aiSettings'

export const aiSettingsService = {
  async get(): Promise<AISettingsRead> {
    return apiGet<AISettingsRead>('/api/v1/ai-settings/')
  },

  async update(data: AISettingsUpdate): Promise<AISettingsRead> {
    return apiPut<AISettingsRead>('/api/v1/ai-settings/', data)
  },

  async test(overrides: AISettingsUpdate = {}): Promise<AISettingsTestResult> {
    return apiPost<AISettingsTestResult>('/api/v1/ai-settings/test', overrides)
  },
}
