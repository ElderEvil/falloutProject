import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createToastMock } from '../../helpers/mocks'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import apiClient from '@/core/plugins/axios'
import * as toastModule from '@/core/composables/useToast'
import {
  AUTH_TOKENS_REFRESHED_EVENT,
  type RefreshedAuthTokens,
} from '@/core/utils/authSessionEvents'

/**
 * Regression coverage for the shared Axios client's auth ownership.
 *
 * The request interceptor is the single place that attaches the bearer token;
 * feature code must not pass it by hand. Every other test in the suite mocks
 * `@/core/plugins/axios`, so nothing exercised the real interceptor before this
 * — which matters because removing the per-call bearer headers depends on it.
 */

const mockToast = createToastMock()

// vitest.setup.ts imports axios before this file runs, so axios.ts is already
// bound to the real useToast; only spying on the shared export intercepts it.
function stubToast(): void {
  vi.spyOn(toastModule, 'useToast').mockReturnValue(
    mockToast as unknown as ReturnType<typeof toastModule.useToast>
  )
}

const originalAdapter = apiClient.defaults.adapter
const originalLocationDescriptor = Object.getOwnPropertyDescriptor(window, 'location')

let locationStub: { href: string }

function captureRequests(): InternalAxiosRequestConfig[] {
  const seen: InternalAxiosRequestConfig[] = []
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    seen.push(config)
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config }
  }
  return seen
}

function statusError(
  config: InternalAxiosRequestConfig,
  status: number,
  data?: unknown,
  headers: Record<string, string> = {}
): AxiosError {
  const response: AxiosResponse = { data, status, statusText: '', headers, config }
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_RESPONSE', config, {}, response)
}

function rejectWithError(
  makeError: (config: InternalAxiosRequestConfig) => AxiosError
): InternalAxiosRequestConfig[] {
  const seen: InternalAxiosRequestConfig[] = []
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    seen.push(config)
    throw makeError(config)
  }
  return seen
}

function failOnceThenResolve(
  makeError: (config: InternalAxiosRequestConfig) => AxiosError
): InternalAxiosRequestConfig[] {
  const seen: InternalAxiosRequestConfig[] = []
  let attempt = 0
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    seen.push(config)
    attempt += 1
    if (attempt === 1) {
      throw makeError(config)
    }
    return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
  }
  return seen
}

beforeEach(() => {
  stubToast()
  locationStub = { href: '' }
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: locationStub,
  })
  vi.clearAllMocks()
  localStorage.clear()
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
  vi.restoreAllMocks()
  if (originalLocationDescriptor) {
    Object.defineProperty(window, 'location', originalLocationDescriptor)
  }
})

describe('axios auth interceptor', () => {
  it('attaches the stored bearer token to a request', async () => {
    localStorage.setItem('token', 'abc123')
    const seen = captureRequests()

    await apiClient.get('/api/v1/thing')

    expect(seen).toHaveLength(1)
    expect(seen[0]?.headers.Authorization).toBe('Bearer abc123')
  })

  it('strips the quotes the token is stored with', async () => {
    localStorage.setItem('token', '"abc123"')
    const seen = captureRequests()

    await apiClient.get('/api/v1/thing')

    expect(seen[0]?.headers.Authorization).toBe('Bearer abc123')
  })

  it('sends no Authorization header when no token is stored', async () => {
    const seen = captureRequests()

    await apiClient.get('/api/v1/thing')

    expect(seen[0]?.headers.Authorization).toBeUndefined()
  })

  it('attaches the token to mutations as well as reads', async () => {
    localStorage.setItem('token', 'abc123')
    const seen = captureRequests()

    await apiClient.put('/api/v1/thing', null, { params: { mode: 'happiness' } })

    expect(seen[0]?.headers.Authorization).toBe('Bearer abc123')
    expect(seen[0]?.params).toEqual({ mode: 'happiness' })
  })
})

describe('axios response interceptor', () => {
  it('maps 400 to Invalid Request and uses a string detail as the message', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'Bad payload' }))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Invalid Request: Bad payload')
  })

  it('maps 401 to Unauthorized when the retried request fails again', async () => {
    rejectWithError((config) => statusError(config, 401))

    await expect(apiClient.get('/api/v1/thing', { _retry: true })).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Unauthorized: Please log in to continue')
  })

  it('maps 403 to Access Denied', async () => {
    rejectWithError((config) => statusError(config, 403))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith(
      "Access Denied: You don't have permission to perform this action"
    )
  })

  it('maps 404 to Not Found', async () => {
    rejectWithError((config) => statusError(config, 404))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Not Found: The requested resource was not found')
  })

  it('maps 422 to Validation Error and formats a FastAPI detail array', async () => {
    rejectWithError((config) =>
      statusError(config, 422, { detail: [{ loc: ['body', 'x'], msg: 'bad' }] })
    )

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Validation Error: body.x: bad')
  })

  it('maps 429 to Rate Limit Exceeded with the default message', async () => {
    rejectWithError((config) => statusError(config, 429))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith(
      'Rate Limit Exceeded: Too many requests. Please slow down and try again.'
    )
  })

  it('includes the Retry-After seconds in the 429 message', async () => {
    rejectWithError((config) => statusError(config, 429, undefined, { 'retry-after': '30' }))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith(
      'Rate Limit Exceeded: Too many requests. Please wait 30 seconds before trying again.'
    )
  })

  it('maps 5xx to Server Error', async () => {
    rejectWithError((config) => statusError(config, 503))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Server Error: Something went wrong on our end')
  })

  it('serialises an object detail as JSON', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: { field: 'x' } }))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Invalid Request: {"field":"x"}')
  })

  it('uses the message key when detail is absent', async () => {
    rejectWithError((config) => statusError(config, 400, { message: 'Custom message' }))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Invalid Request: Custom message')
  })

  it('uses a raw string response body as the message', async () => {
    rejectWithError((config) => statusError(config, 400, 'Raw failure'))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith('Invalid Request: Raw failure')
  })

  it('suppresses the toast when _skipErrorNotification is set', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'boom' }))

    await expect(
      apiClient.get('/api/v1/thing', { _skipErrorNotification: true })
    ).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('maps a network error to Network Error', async () => {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
      throw new AxiosError('Network Error', 'ERR_NETWORK', config, {})
    }

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith(
      'Network Error: Unable to reach the server. Please check your connection.'
    )
  })

  it('rejects untouched when the error is not an AxiosError', async () => {
    const boom = new Error('boom')
    apiClient.defaults.adapter = (): Promise<AxiosResponse> => Promise.reject(boom)

    await expect(apiClient.get('/api/v1/thing')).rejects.toBe(boom)

    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('refreshes the token on 401 and retries the original request', async () => {
    localStorage.setItem('token', JSON.stringify('old-token'))
    localStorage.setItem('refreshToken', JSON.stringify('refresh-1'))
    const seen = failOnceThenResolve((config) => statusError(config, 401))

    const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
      data: { access_token: 'new-token', refresh_token: 'refresh-2' },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {} as InternalAxiosRequestConfig,
    })

    const refreshed: RefreshedAuthTokens[] = []
    const onRefreshed = (event: Event): void => {
      refreshed.push((event as CustomEvent<RefreshedAuthTokens>).detail)
    }
    window.addEventListener(AUTH_TOKENS_REFRESHED_EVENT, onRefreshed)

    await apiClient.get('/api/v1/thing')

    window.removeEventListener(AUTH_TOKENS_REFRESHED_EVENT, onRefreshed)

    expect(postSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/refresh'),
      { refresh_token: 'refresh-1' }
    )
    expect(localStorage.getItem('token')).toBe(JSON.stringify('new-token'))
    expect(localStorage.getItem('refreshToken')).toBe(JSON.stringify('refresh-2'))
    expect(refreshed).toEqual([{ token: 'new-token', refreshToken: 'refresh-2' }])
    expect(seen).toHaveLength(2)
    expect(seen[1]?.headers.Authorization).toBe('Bearer new-token')
  })

  it('clears auth data and redirects to /login when the refresh call fails', async () => {
    localStorage.setItem('token', JSON.stringify('old-token'))
    localStorage.setItem('refreshToken', JSON.stringify('refresh-1'))
    localStorage.setItem('user', JSON.stringify({ id: 'u1' }))
    rejectWithError((config) => statusError(config, 401))
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('refresh unavailable'))

    await expect(apiClient.get('/api/v1/thing')).rejects.toThrow('refresh unavailable')

    expect(locationStub.href).toBe('/login')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('clears auth data and redirects to /login on 401 without a refresh token', async () => {
    localStorage.setItem('token', JSON.stringify('old-token'))
    localStorage.setItem('user', JSON.stringify({ id: 'u1' }))
    rejectWithError((config) => statusError(config, 401))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(locationStub.href).toBe('/login')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(mockToast.error).not.toHaveBeenCalled()
  })
})
