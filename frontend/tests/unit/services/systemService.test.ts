import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApiClientMock } from '../helpers/mocks'
import { apiRequest } from '@/core/utils/api'

vi.mock('@/core/utils/api', () => createApiClientMock())

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
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: mockInfo })

      const result = await systemService.getInfo()

      expect(apiRequest).toHaveBeenCalledWith('get', '/api/v1/system/info')
      expect(result.data).toEqual(mockInfo)
    })

    it('should propagate errors', async () => {
      const error = new Error('Network error')
      vi.mocked(apiRequest).mockRejectedValueOnce(error)

      await expect(systemService.getInfo()).rejects.toThrow('Network error')
    })
  })
})
