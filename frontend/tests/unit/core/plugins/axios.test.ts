import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import { ref } from 'vue'
import { createPinia, setActivePinia, disposePinia, getActivePinia } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useChatActions } from '@/modules/chat/composables/useChatActions'
import { createToastMock } from '../../helpers/mocks'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import apiClient from '@/core/plugins/axios'
import { handleStoreError } from '@/core/utils/errorHandler'
import { apiGet, ApiError } from '@/core/utils/api'
import { chatApi } from '@/modules/chat/api/chat'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
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
  apiClient.defaults.adapter = async (
    config: InternalAxiosRequestConfig
  ): Promise<AxiosResponse> => {
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
  return new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_RESPONSE',
    config,
    {},
    response
  )
}

function rejectWithError(
  makeError: (config: InternalAxiosRequestConfig) => AxiosError
): InternalAxiosRequestConfig[] {
  const seen: InternalAxiosRequestConfig[] = []
  apiClient.defaults.adapter = async (
    config: InternalAxiosRequestConfig
  ): Promise<AxiosResponse> => {
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
  apiClient.defaults.adapter = async (
    config: InternalAxiosRequestConfig
  ): Promise<AxiosResponse> => {
    seen.push(config)
    attempt += 1
    if (attempt === 1) {
      throw makeError(config)
    }
    return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
  }
  return seen
}

/** Asserts a single request was sent and returns it, so callers never index loosely. */
function soleRequest(seen: InternalAxiosRequestConfig[]): InternalAxiosRequestConfig {
  expect(seen).toHaveLength(1)
  return seen[0]!
}

/** A refresh call the test holds open, so it can mutate storage mid-flight. */
function pendingRefresh(): { post: Mock; resolveRefresh: (data: unknown) => void } {
  let finish!: (value: unknown) => void
  const post = vi.spyOn(axios, 'post').mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      })
  )
  return { post, resolveRefresh: (data: unknown) => finish({ data }) }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(window, 'addEventListener')
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
  const pinia = getActivePinia()
  if (pinia) disposePinia(pinia)
  for (const [type, listener] of vi.mocked(window.addEventListener).mock.calls) {
    if (type === AUTH_TOKENS_REFRESHED_EVENT || type === 'auth-session-expired')
      window.removeEventListener(type, listener)
  }
  vi.restoreAllMocks()
  if (originalLocationDescriptor) {
    Object.defineProperty(window, 'location', originalLocationDescriptor)
  }
})

describe('axios auth interceptor', () => {
  it.each([
    ['attaches the stored bearer token to a request', 'abc123', 'Bearer abc123'],
    ['strips the quotes the token is stored with', JSON.stringify('abc123'), 'Bearer abc123'],
    ['sends no Authorization header when no token is stored', null, undefined],
  ])('%s', async (_label, stored, expected) => {
    if (stored !== null) localStorage.setItem('token', stored)
    const seen = captureRequests()

    await apiClient.get('/api/v1/thing')

    expect(soleRequest(seen).headers.Authorization).toBe(expected)
  })

  it('attaches the token to mutations as well as reads', async () => {
    localStorage.setItem('token', 'abc123')
    const seen = captureRequests()

    await apiClient.put('/api/v1/thing', null, { params: { mode: 'happiness' } })

    const request = soleRequest(seen)
    expect(request.headers.Authorization).toBe('Bearer abc123')
    expect(request.params).toEqual({ mode: 'happiness' })
  })
})

describe('axios response interceptor', () => {
  it('notifies once when a request error propagates through action and UI handlers', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'Room is full' }))
    const action = useAsyncAction(() => apiClient.post('/api/v1/assign'), { rethrow: true })
    try {
      await action.run()
    } catch (error) {
      handleStoreError(error, 'Could not assign dweller')
    }
    expect(mockToast.error).toHaveBeenCalledTimes(1)
    expect(mockToast.error).toHaveBeenCalledWith('Invalid Request: Room is full')
  })

  it('preserves notification ownership through normalized API error causes', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'Insufficient caps' }))
    try {
      await apiGet('/api/v1/vault')
    } catch (error) {
      expect(handleStoreError(error, 'Could not build room')).toBe('Insufficient caps')
    }
    expect(mockToast.error).toHaveBeenCalledTimes(1)
  })

  it('notifies a caller-owned failure once when HTTP notifications are disabled', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'Not enough supplies' }))
    try {
      await apiClient.post('/api/v1/heal', null, { _skipErrorNotification: true })
    } catch (error) {
      handleStoreError(error, 'Could not heal')
      handleStoreError(error, 'Medical action failed')
    }
    expect(mockToast.error).toHaveBeenCalledTimes(1)
    expect(mockToast.error).toHaveBeenCalledWith('Could not heal: Not enough supplies')
  })

  it('preserves notification ownership when a room error exposes its detail', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'Insufficient caps' }))
    try {
      await useRoomStore().buildRoom('Diner', 0, 0, 'token', 'vault-1')
    } catch (error) {
      expect((error as Error).message).toBe('Insufficient caps')
      handleStoreError(error, 'Build failed')
    }
    expect(mockToast.error).toHaveBeenCalledTimes(1)
  })

  it('leaves a legacy overflow error for the modal to explain once', async () => {
    rejectWithError((config) => statusError(config, 404))
    await expect(
      useExplorationStore().resolveOverflowItem('exp-1', 'sell', 0)
    ).rejects.toBeInstanceOf(ApiError)
    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('handles cyclic error causes without repeated notifications', () => {
    const error = new Error('Offline')
    error.cause = error
    handleStoreError(error, 'Failed')
    handleStoreError(error, 'Failed again')
    expect(mockToast.error).toHaveBeenCalledTimes(1)
  })

  it('keeps separate failures visible even when their messages match', () => {
    handleStoreError(new Error('Unavailable'), 'Failed')
    handleStoreError(new Error('Unavailable'), 'Failed')
    expect(mockToast.error).toHaveBeenCalledTimes(2)
  })

  const statusCases: Array<{
    label: string
    status: number
    body?: unknown
    headers?: Record<string, string>
    message: string
  }> = [
    {
      label: 'maps 400 to Invalid Request and uses a string detail as the message',
      status: 400,
      body: { detail: 'Bad payload' },
      message: 'Invalid Request: Bad payload',
    },
    {
      label: 'maps 403 to Access Denied',
      status: 403,
      message: "Access Denied: You don't have permission to perform this action",
    },
    {
      label: 'maps 404 to Not Found',
      status: 404,
      message: 'Not Found: The requested resource was not found',
    },
    {
      label: 'maps 422 to Validation Error and formats a FastAPI detail array',
      status: 422,
      body: { detail: [{ loc: ['body', 'x'], msg: 'bad' }] },
      message: 'Validation Error: body.x: bad',
    },
    {
      label: 'maps 429 to Rate Limit Exceeded with the default message',
      status: 429,
      message: 'Rate Limit Exceeded: Too many requests. Please slow down and try again.',
    },
    {
      label: 'includes the Retry-After seconds in the 429 message',
      status: 429,
      headers: { 'retry-after': '30' },
      message:
        'Rate Limit Exceeded: Too many requests. Please wait 30 seconds before trying again.',
    },
    {
      label: 'maps 5xx to Server Error',
      status: 503,
      message: 'Server Error: Something went wrong on our end',
    },
    {
      label: 'serialises an object detail as JSON',
      status: 400,
      body: { detail: { field: 'x' } },
      message: 'Invalid Request: {"field":"x"}',
    },
    {
      label: 'uses the message key when detail is absent',
      status: 400,
      body: { message: 'Custom message' },
      message: 'Invalid Request: Custom message',
    },
    {
      label: 'uses a raw string response body as the message',
      status: 400,
      body: 'Raw failure',
      message: 'Invalid Request: Raw failure',
    },
  ]

  it.each(statusCases)('$label', async ({ status, body, headers, message }) => {
    rejectWithError((config) => statusError(config, status, body, headers))

    await expect(apiClient.get('/api/v1/thing')).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).toHaveBeenCalledWith(message)
  })

  it('ends the session without toast spam when the retried request is still unauthorized', async () => {
    rejectWithError((config) => statusError(config, 401))

    await expect(apiClient.get('/api/v1/thing', { _retry: true })).rejects.toBeInstanceOf(
      AxiosError
    )

    expect(mockToast.error).not.toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('suppresses the toast when _skipErrorNotification is set', async () => {
    rejectWithError((config) => statusError(config, 400, { detail: 'boom' }))

    await expect(
      apiClient.get('/api/v1/thing', { _skipErrorNotification: true })
    ).rejects.toBeInstanceOf(AxiosError)

    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it('maps a network error to Network Error', async () => {
    apiClient.defaults.adapter = async (
      config: InternalAxiosRequestConfig
    ): Promise<AxiosResponse> => {
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

    expect(postSpy).toHaveBeenCalledWith(expect.stringContaining('/api/v1/auth/refresh'), {
      refresh_token: 'refresh-1',
    })
    expect(localStorage.getItem('token')).toBe(JSON.stringify('new-token'))
    expect(localStorage.getItem('refreshToken')).toBe(JSON.stringify('refresh-2'))
    expect(refreshed).toEqual([{ token: 'new-token', refreshToken: 'refresh-2' }])
    expect(seen).toHaveLength(2)
    expect(seen[1]?.headers.Authorization).toBe('Bearer new-token')
  })

  it('refreshes an expired token before sending the protected request', async () => {
    const expiredToken = `header.${btoa(JSON.stringify({ exp: 1 }))}.signature`
    localStorage.setItem('token', expiredToken)
    localStorage.setItem('refreshToken', 'refresh-expired')
    const seen = captureRequests()
    const refresh = vi
      .spyOn(axios, 'post')
      .mockResolvedValue({ data: { access_token: 'fresh-token' } })
    await apiClient.get('/protected')
    expect(refresh).toHaveBeenCalledTimes(1)
    const request = soleRequest(seen)
    expect(request.headers.Authorization).toBe('Bearer fresh-token')
  })

  it('does not restore credentials after logout while refresh is pending', async () => {
    localStorage.setItem('token', 'old-token')
    localStorage.setItem('refreshToken', 'refresh-logout-race')
    rejectWithError((config) => statusError(config, 401))
    const { post, resolveRefresh } = pendingRefresh()
    const rejected = expect(apiClient.get('/protected')).rejects.toThrow('Session changed')
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    localStorage.clear()
    resolveRefresh({ access_token: 'late-token', refresh_token: 'late-refresh' })
    await rejected
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('uses credentials rotated by another tab while refresh is pending', async () => {
    const token = (version: number) =>
      `header.${btoa(JSON.stringify({ sub: 'same-user', version }))}.signature`
    localStorage.setItem('token', token(1))
    localStorage.setItem('refreshToken', 'old-refresh')
    const seen = failOnceThenResolve((config) => statusError(config, 401))
    const { post, resolveRefresh } = pendingRefresh()
    const request = apiClient.get('/protected')
    const completed = expect(request).resolves.toMatchObject({ status: 200 })
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    localStorage.setItem('token', token(2))
    localStorage.setItem('refreshToken', 'rotated-refresh')
    resolveRefresh({ access_token: 'stale-token', refresh_token: 'stale-refresh' })
    await completed
    expect(seen).toHaveLength(2)
    expect(seen[1]?.headers.Authorization).toBe(`Bearer ${token(2)}`)
    expect(localStorage.getItem('token')).toBe(token(2))
    expect(localStorage.getItem('refreshToken')).toBe('rotated-refresh')
    expect(locationStub.href).toBe('')
  })

  it('does not retry an old request under a different account', async () => {
    const token = (sub: string) => `header.${btoa(JSON.stringify({ sub }))}.signature`
    localStorage.setItem('token', token('old-user'))
    localStorage.setItem('refreshToken', 'old-refresh')
    const seen = failOnceThenResolve((config) => statusError(config, 401))
    const { post, resolveRefresh } = pendingRefresh()
    const request = expect(apiClient.post('/protected-action')).rejects.toMatchObject({
      code: 'ERR_CANCELED',
    })
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    localStorage.setItem('token', token('new-user'))
    localStorage.setItem('refreshToken', 'new-login-refresh')
    resolveRefresh({ access_token: 'stale-token', refresh_token: 'stale-refresh' })
    await request
    expect(seen).toHaveLength(1)
    expect(localStorage.getItem('token')).toBe(token('new-user'))
    expect(localStorage.getItem('refreshToken')).toBe('new-login-refresh')
    expect(locationStub.href).toBe('')
  })

  it('shares one refresh between simultaneous unauthorized requests', async () => {
    localStorage.setItem('token', 'old-token')
    localStorage.setItem('refreshToken', 'refresh-concurrent')
    const seen: string[] = []
    apiClient.defaults.adapter = async (config) => {
      seen.push(String(config.headers.Authorization))
      if (!config._retry) throw statusError(config, 401)
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config }
    }
    const { post, resolveRefresh } = pendingRefresh()
    const requests = Promise.all([apiClient.get('/first'), apiClient.get('/second')])
    await vi.waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    resolveRefresh({ access_token: 'fresh-token', refresh_token: 'refresh-next' })
    await requests
    expect(post).toHaveBeenCalledTimes(1)
    expect(seen).toEqual([
      'Bearer old-token',
      'Bearer old-token',
      'Bearer fresh-token',
      'Bearer fresh-token',
    ])
  })

  it('keeps the session after a temporary refresh failure', async () => {
    localStorage.setItem('token', 'old-token')
    localStorage.setItem('refreshToken', 'refresh-temporary')
    rejectWithError((config) => statusError(config, 401))
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('Network down'))
    await expect(apiClient.get('/thing')).rejects.toThrow('Network down')
    expect(localStorage.getItem('token')).toBe('old-token')
    expect(locationStub.href).toBe('')
  })

  it('clears auth data and redirects to /login when the refresh call fails', async () => {
    localStorage.setItem('token', JSON.stringify('old-token'))
    localStorage.setItem('refreshToken', JSON.stringify('refresh-1'))
    localStorage.setItem('user', JSON.stringify({ id: 'u1' }))
    rejectWithError((config) => statusError(config, 401))
    vi.spyOn(axios, 'post').mockRejectedValue(
      Object.assign(new Error('refresh unavailable'), { response: { status: 400 } })
    )

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

    await expect(apiClient.get('/api/v1/thing')).rejects.toMatchObject({ status: 401 })

    expect(locationStub.href).toBe('/login')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(mockToast.error).not.toHaveBeenCalled()
  })
})

describe('chat exploration notifications across UI and store', () => {
  const chatActions = () =>
    useChatActions({
      dwellerId: 'dweller-1',
      dwellerName: 'Lucy',
      messages: ref([]),
      vaultId: 'vault-1',
    })

  it('confirms training once after moving the dweller into a training room', async () => {
    useAuthStore().token = 'test-token'
    useDwellerStore().filter.dwellers = [{ id: 'dweller-1', room_id: null }] as never
    useRoomStore().rooms = [
      { id: 'training-1', category: 'training', ability: 'Strength', size: 3 },
    ] as never
    captureRequests()
    await chatActions().handleActionConfirm(
      { action_type: 'start_training', stat: 'strength', reason: 'Train strength' },
      0
    )
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.info).not.toHaveBeenCalled()
    expect(mockToast.error).not.toHaveBeenCalled()
  })

  it.each([0, 100])('confirms the recall action once at %s percent progress', async (progress) => {
    useAuthStore().token = 'test-token'
    apiClient.defaults.adapter = async (config): Promise<AxiosResponse> => ({
      config,
      status: 200,
      statusText: 'OK',
      headers: {},
      data: config.url?.endsWith('/progress')
        ? { progress_percentage: progress }
        : {
            exploration: { id: 'exploration-1', dweller_id: 'dweller-1', status: 'returning' },
            rewards_summary: progress === 100 ? { caps: 10 } : undefined,
          },
    })
    await chatActions().handleActionConfirm(
      { action_type: 'recall_exploration', exploration_id: 'exploration-1', reason: 'Return home' },
      0
    )
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.info).not.toHaveBeenCalled()
    expect(mockToast.error).not.toHaveBeenCalled()
  })
})

it.each([false, true])(
  'preserves voice multipart through the real chat transport (returnAudio=%s)',
  async (returnAudio) => {
    const requests = captureRequests()
    const audio = new Blob(['voice bytes'], { type: 'audio/webm' })

    await chatApi.sendVoiceMessage('dweller-voice', audio, { returnAudio })

    const request = requests[0]!
    expect(request.url).toBe('/api/v1/chat/dweller-voice/voice')
    expect(request.params).toEqual({ return_audio: returnAudio })
    expect(request.headers.get('Content-Type')).toBe('multipart/form-data')
    expect(request.data).toBeInstanceOf(FormData)
    const file = (request.data as FormData).get('audio_file') as File
    expect(file).toBeInstanceOf(File)
    expect(file.name).toBe('recording.webm')
    expect(file.type).toBe('audio/webm')
    const content = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = () => reject(reader.error)
      reader.readAsText(file)
    })
    expect(content).toBe('voice bytes')

    await chatApi.sendMessage('dweller-voice', 'hello')
    expect(requests[1]!.headers.get('Content-Type')).toBe('application/json')
    expect(requests[1]!.data).toBe(JSON.stringify({ message: 'hello' }))
  }
)
