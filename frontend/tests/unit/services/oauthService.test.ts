import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { oauthService } from '@/modules/auth/services/oauthService'
import { apiRequest } from '@/core/utils/api'

vi.mock('@/core/utils/api', () => ({ apiRequest: vi.fn() }))

describe('oauthService', () => {
  beforeEach(() => vi.mocked(apiRequest).mockReset())

  it('loads enabled providers', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: { google: true, github: false } } as never)

    await expect(oauthService.getProviders()).resolves.toEqual({ google: true, github: false })
    expect(apiRequest).toHaveBeenCalledWith(
      'get',
      '/api/v1/auth/oauth/providers',
      undefined,
      expect.objectContaining({ skipErrorNotification: true })
    )
  })

  it('builds the backend authorize URL', () => {
    expect(oauthService.authorizeUrl('github')).toMatch(/\/api\/v1\/auth\/oauth\/github\/authorize$/)
  })

  it('redeems the handoff with credentials', async () => {
    vi.mocked(apiRequest).mockResolvedValue({ data: { access_token: 'a', refresh_token: 'r' } } as never)

    await oauthService.redeemHandoff('code-1')

    expect(apiRequest).toHaveBeenCalledWith(
      'post',
      '/api/v1/auth/oauth/handoff',
      { code: 'code-1' },
      expect.objectContaining({ withCredentials: true, skipErrorNotification: true })
    )
  })
})
