import apiClient from '@/core/plugins/axios'
import type { AxiosResponse } from 'axios'
import type { InfoResponse } from '../types/system'

export const systemService = {
  async getInfo(): Promise<AxiosResponse<InfoResponse>> {
    return await apiClient.get('/api/v1/system/info')
  },
}
