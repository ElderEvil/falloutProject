import { describe, it, expect, beforeEach, vi } from 'vitest'
import apiClient from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

import { systemService } from '@/modules/profile/services/systemService'

describe('systemService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getInfo', () => {
    it('should fetch system info from correct endpoint', async () => {
      const mockInfo = {
        app_version: '2.18.0',
        api_version: 'v1',
        environment: 'development',
        python_version: '3.13.0',
      }
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockInfo })

      const result = await systemService.getInfo()

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/system/info')
      expect(result.data).toEqual(mockInfo)
    })

    it('should propagate errors', async () => {
      const error = new Error('Network error')
      vi.mocked(apiClient.get).mockRejectedValueOnce(error)

      await expect(systemService.getInfo()).rejects.toThrow('Network error')
    })
  })
})
