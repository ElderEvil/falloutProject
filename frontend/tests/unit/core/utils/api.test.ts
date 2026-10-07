import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock } from '../../helpers/mocks'
import type { AxiosResponse } from 'axios'
import apiClient from '@/core/plugins/axios'
import { ApiError, apiGet, apiPost, apiRequest, authHeaders } from '@/core/utils/api'
import { getErrorMessage } from '@/core/types/utils'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

function respond(data: unknown): AxiosResponse {
  return { data } as unknown as AxiosResponse
}

describe('api boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('unwraps response.data through apiGet', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce(respond({ id: 1 }))

    await expect(apiGet<{ id: number }>('/api/v1/thing')).resolves.toEqual({ id: 1 })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/thing')
  })

  it('never passes a bearer token by hand', async () => {
    localStorage.setItem('token', '"abc123"')
    vi.mocked(apiClient.get).mockResolvedValueOnce(respond({}))

    await apiGet('/api/v1/thing')

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/thing')
  })

  it('forwards params and skipErrorNotification to the axios config', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce(respond({}))

    await apiPost('/api/v1/thing', { a: 1 }, { params: { q: 'x' }, skipErrorNotification: true })

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/thing', { a: 1 }, {
      params: { q: 'x' },
      _skipErrorNotification: true,
    })
  })

  it('normalizes failures to ApiError with detail, fields and headers', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce({
      response: {
        status: 422,
        data: { detail: [{ loc: ['body', 'email'], msg: 'invalid email' }] },
        headers: { 'x-request-id': 'abc' },
      },
    })

    const error = await apiGet('/api/v1/thing').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)

    const apiError = error as ApiError
    expect(apiError.status).toBe(422)
    expect(apiError.fields).toEqual({ 'body.email': 'invalid email' })
    expect(apiError.headers).toEqual({ 'x-request-id': 'abc' })
    expect(apiError.cause).toBeDefined()
  })

  it('apiRequest returns the full response untouched', async () => {
    const response = respond({ id: 1 })
    vi.mocked(apiClient.get).mockResolvedValueOnce(response)

    await expect(apiRequest('get', '/api/v1/thing')).resolves.toBe(response)
  })

  it('authHeaders reads the stored token without quotes', () => {
    expect(authHeaders()).toEqual({})

    localStorage.setItem('token', '"abc123"')
    expect(authHeaders()).toEqual({ Authorization: 'Bearer abc123' })
  })
})

describe('getErrorMessage on both error shapes', () => {
  it('reads a normalized ApiError detail', () => {
    expect(getErrorMessage(new ApiError({ detail: 'nope' }))).toBe('nope')
  })

  it('flattens a FastAPI validation array carried by ApiError', () => {
    expect(
      getErrorMessage(new ApiError({ detail: [{ loc: ['body', 'email'], msg: 'invalid email' }] }))
    ).toBe('body.email: invalid email')
  })

  it('keeps raw axios-shaped errors working', () => {
    expect(getErrorMessage({ response: { data: { detail: 'raw detail' } } })).toBe('raw detail')
  })
})
