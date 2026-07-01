import { describe, it, expect, beforeEach, vi, afterEach, type Mock } from 'vitest'
import {
  apiGet,
  apiPost,
  apiPut,
  apiPatch,
  apiDelete,
  ApiError,
  registerAuthSyncCallback,
} from '@/core/plugins/httpClient'
import { useToast } from '@/core/composables/useToast'

vi.mock('@/core/composables/useToast')

const mockToastError = vi.fn()

function mockFetchResponse(
  status: number,
  data?: unknown,
  headers: Record<string, string> = {}
): Response {
  const allHeaders = status < 400
    ? { 'content-type': 'application/json', ...headers }
    : headers
  return {
    ok: status < 400,
    status,
    headers: {
      get: (name: string) => allHeaders[name.toLowerCase()] ?? null,
    },
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as unknown as Response
}

describe('httpClient', () => {
  let fetchMock: Mock
  let toastErrorMock: Mock
  const originalLocation = window.location

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    vi.mocked(useToast).mockReturnValue({
      show: vi.fn(),
      remove: vi.fn(),
      success: vi.fn(),
      error: mockToastError,
      warning: vi.fn(),
      info: vi.fn(),
      toasts: { value: [] },
    } as unknown as ReturnType<typeof useToast>)
    toastErrorMock = mockToastError
    vi.clearAllMocks()
    localStorage.clear()

    // @ts-expect-error - mocking window.location
    delete window.location
    // @ts-expect-error - mocking window.location
    window.location = { href: '' }

    // Reset auth sync callback
    registerAuthSyncCallback(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    // @ts-expect-error - restoring window.location
    window.location = originalLocation
  })

  describe('auth header injection', () => {
    it('should inject Bearer token from localStorage into request headers', async () => {
      localStorage.setItem('token', '"test-access-token"')
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiGet('/api/v1/users/me')

      expect(fetchMock).toHaveBeenCalledTimes(1)
      const callArgs = fetchMock.mock.calls[0]
      expect(callArgs[1].headers.Authorization).toBe('Bearer test-access-token')
    })

    it('should not inject Authorization header when no token exists', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiGet('/api/v1/users/me')

      const callArgs = fetchArgs(fetchMock)
      expect(callArgs[1].headers.Authorization).toBeUndefined()
    })

    it('should handle VueUse quote-mangled tokens correctly', async () => {
      localStorage.setItem('token', '"quoted-token-value"')
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiGet('/api/v1/users/me')

      const callArgs = fetchArgs(fetchMock)
      expect(callArgs[1].headers.Authorization).toBe('Bearer quoted-token-value')
    })
  })

  describe('401 token refresh and retry', () => {
    it('should refresh token on 401 and retry original request with new token', async () => {
      localStorage.setItem('token', '"old-token"')
      localStorage.setItem('refreshToken', '"old-refresh"')

      // First call: 401 unauthorized
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Unauthorized' }))
      // Refresh call: success
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(200, {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
        })
      )
      // Retry original call: success
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 42 }))

      const result = await apiGet('/api/v1/users/me')

      expect(fetchMock).toHaveBeenCalledTimes(3)

      // Original request
      const originalCall = fetchMock.mock.calls[0]
      expect(originalCall[1].headers.Authorization).toBe('Bearer old-token')

      // Refresh request
      const refreshCall = fetchMock.mock.calls[1]
      expect(refreshCall[0]).toContain('/api/v1/auth/refresh')
      expect(JSON.parse(refreshCall[1].body)).toEqual({ refresh_token: 'old-refresh' })

      // Retry request
      const retryCall = fetchMock.mock.calls[2]
      expect(retryCall[1].headers.Authorization).toBe('Bearer new-access-token')

      expect(result).toEqual({ id: 42 })

      // Token updated in localStorage
      expect(localStorage.getItem('token')).toBe('"new-access-token"')
    })

    it('should only retry once and fail on second 401', async () => {
      localStorage.setItem('token', '"old-token"')
      localStorage.setItem('refreshToken', '"old-refresh"')

      // First call: 401
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Unauthorized' }))
      // Refresh: success
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(200, {
          access_token: 'new-token',
          refresh_token: 'new-refresh',
        })
      )
      // Retry: 401 again
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Still unauthorized' }))

      await expect(apiGet('/api/v1/users/me')).rejects.toThrow(ApiError)

      expect(fetchMock).toHaveBeenCalledTimes(3)
    })
  })

  describe('refresh failure handling', () => {
    it('should clear auth data and redirect to /login when refresh fails', async () => {
      localStorage.setItem('token', '"old-token"')
      localStorage.setItem('refreshToken', '"old-refresh"')
      localStorage.setItem('user', '{"id":1}')

      // First call: 401
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Unauthorized' }))
      // Refresh call: 401 failure
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Invalid refresh token' }))

      await expect(apiGet('/api/v1/users/me')).rejects.toThrow(ApiError)

      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('refreshToken')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
      expect(window.location.href).toBe('/login')
    })

    it('should redirect to /login when no refresh token exists on 401', async () => {
      localStorage.setItem('token', '"old-token"')
      // No refresh token

      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Unauthorized' }))

      await expect(apiGet('/api/v1/users/me')).rejects.toThrow(ApiError)

      expect(localStorage.getItem('token')).toBeNull()
      expect(window.location.href).toBe('/login')
    })

    it('should call registered auth sync callback with new refresh token on success', async () => {
      localStorage.setItem('token', '"old-token"')
      localStorage.setItem('refreshToken', '"old-refresh"')

      const syncCallback = vi.fn()
      registerAuthSyncCallback(syncCallback)

      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, { detail: 'Unauthorized' }))
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(200, {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
        })
      )
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiGet('/api/v1/users/me')

      expect(syncCallback).toHaveBeenCalledWith('new-refresh-token')
    })
  })

  describe('422 validation error parsing', () => {
    it('should parse FastAPI validation errors into structured message', async () => {
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(422, {
          detail: [
            { loc: ['body', 'username'], msg: 'Field required', type: 'missing' },
            { loc: ['body', 'email'], msg: 'Invalid email format', type: 'value_error' },
          ],
        })
      )

      await expect(apiPost('/api/v1/users/open', {})).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith(
        'Validation Error: body.username: Field required, body.email: Invalid email format'
      )
    })

    it('should handle single string detail in 422', async () => {
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(422, { detail: 'Invalid input data' })
      )

      await expect(apiPost('/api/v1/test', {})).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Validation Error: Invalid input data')
    })
  })

  describe('429 rate limit handling', () => {
    it('should extract Retry-After header and show wait message', async () => {
      fetchMock.mockResolvedValueOnce(
        mockFetchResponse(
          429,
          { detail: 'Rate limit exceeded' },
          { 'retry-after': '30' }
        )
      )

      await expect(apiGet('/api/v1/data')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith(
        'Rate Limit Exceeded: Too many requests. Please wait 30 seconds before trying again.'
      )
    })

    it('should show default rate limit message when Retry-After is missing', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(429, {}))

      await expect(apiGet('/api/v1/data')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith(
        'Rate Limit Exceeded: Too many requests. Please slow down and try again.'
      )
    })
  })

  describe('5xx server error handling', () => {
    it('should map 500 to Server Error toast', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(500, {}))

      await expect(apiGet('/api/v1/data')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Server Error: Something went wrong on our end')
    })

    it('should map 502 to Server Error toast', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(502, {}))

      await expect(apiGet('/api/v1/data')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Server Error: Something went wrong on our end')
    })
  })

  describe('network error handling', () => {
    it('should map fetch failure to Network Error toast', async () => {
      fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      await expect(apiGet('/api/v1/data')).rejects.toThrow('Network Error')

      expect(toastErrorMock).toHaveBeenCalledWith(
        'Network Error: Unable to reach the server. Please check your connection.'
      )
    })
  })

  describe('_skipErrorNotification opt-out', () => {
    it('should suppress toast when _skipErrorNotification is true', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(400, { detail: 'Bad request' }))

      await expect(
        apiGet('/api/v1/data', { _skipErrorNotification: true })
      ).rejects.toThrow(ApiError)

      expect(toastErrorMock).not.toHaveBeenCalled()
    })

    it('should show toast when _skipErrorNotification is false', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(400, { detail: 'Bad request' }))

      await expect(
        apiGet('/api/v1/data', { _skipErrorNotification: false })
      ).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Invalid Request: Bad request')
    })

    it('should show toast when _skipErrorNotification is undefined', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(404, {}))

      await expect(apiGet('/api/v1/data')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Not Found: The requested resource was not found')
    })
  })

  describe('HTTP methods', () => {
    it('should send GET request', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { items: [] }))

      await apiGet('/api/v1/items')

      expect(fetchMock.mock.calls[0][1].method).toBe('GET')
    })

    it('should send POST request with body', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(201, { id: 1 }))

      await apiPost('/api/v1/items', { name: 'test' })

      expect(fetchMock.mock.calls[0][1].method).toBe('POST')
      expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ name: 'test' }))
    })

    it('should send PUT request with body', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiPut('/api/v1/items/1', { name: 'updated' })

      expect(fetchMock.mock.calls[0][1].method).toBe('PUT')
    })

    it('should send PATCH request with body', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1 }))

      await apiPatch('/api/v1/items/1', { name: 'patched' })

      expect(fetchMock.mock.calls[0][1].method).toBe('PATCH')
    })

    it('should send DELETE request', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(204, undefined))

      await apiDelete('/api/v1/items/1')

      expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
    })
  })

  describe('ApiError class', () => {
    it('should expose status and detail properties', () => {
      const error = new ApiError(404, 'Not found')

      expect(error.status).toBe(404)
      expect(error.detail).toBe('Not found')
      expect(error.message).toBe('Not found')
      expect(error.name).toBe('ApiError')
    })

    it('should handle object detail', () => {
      const detail = { field: 'invalid' }
      const error = new ApiError(422, detail)

      expect(error.status).toBe(422)
      expect(error.detail).toEqual(detail)
      expect(error.message).toBe(JSON.stringify(detail))
    })
  })

  describe('error status code mapping', () => {
    it('should map 400 to Invalid Request', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(400, { detail: 'Bad params' }))

      await expect(apiGet('/api/v1/test')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Invalid Request: Bad params')
    })

    it('should map 401 to Unauthorized', async () => {
      localStorage.setItem('refreshToken', '"refresh"')
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, {}))
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { access_token: 'new', refresh_token: 'new' }))
      fetchMock.mockResolvedValueOnce(mockFetchResponse(401, {}))

      await expect(apiGet('/api/v1/test')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Unauthorized: Please log in to continue')
    })

    it('should map 403 to Access Denied', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(403, {}))

      await expect(apiGet('/api/v1/test')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith(
        "Access Denied: You don't have permission to perform this action"
      )
    })

    it('should map 404 to Not Found', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(404, {}))

      await expect(apiGet('/api/v1/test')).rejects.toThrow(ApiError)

      expect(toastErrorMock).toHaveBeenCalledWith('Not Found: The requested resource was not found')
    })
  })

  describe('return value', () => {
    it('should return parsed JSON directly without .data wrapper', async () => {
      fetchMock.mockResolvedValueOnce(mockFetchResponse(200, { id: 1, name: 'test' }))

      const result = await apiGet('/api/v1/item')

      expect(result).toEqual({ id: 1, name: 'test' })
      expect(result).not.toHaveProperty('data')
    })
  })
})

function fetchArgs(mock: Mock): [string, RequestInit] {
  return [mock.mock.calls[0][0], mock.mock.calls[0][1]]
}
