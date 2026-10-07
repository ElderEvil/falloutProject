import { apiRequest } from '@/core/utils/api'
import type { AxiosResponse } from 'axios'
import type { InfoResponse } from '../types/system'

export const systemService = {
  async getInfo(): Promise<AxiosResponse<InfoResponse>> {
    return await apiRequest<InfoResponse>('get', '/api/v1/system/info')
  },
}
