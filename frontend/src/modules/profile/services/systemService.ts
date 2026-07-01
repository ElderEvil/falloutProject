import { apiGet } from '@/core/plugins/httpClient'
import type { InfoResponse } from '../types/system'

export const systemService = {
  async getInfo(): Promise<InfoResponse> {
    return apiGet<InfoResponse>('/api/v1/system/info')
  },
}
