import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import apiClient from '@/core/plugins/axios'

/**
 * Regression coverage for the shared Axios client's auth ownership.
 *
 * The request interceptor is the single place that attaches the bearer token;
 * feature code must not pass it by hand. Every other test in the suite mocks
 * `@/core/plugins/axios`, so nothing exercised the real interceptor before this
 * — which matters because removing the per-call bearer headers depends on it.
 */

const originalAdapter = apiClient.defaults.adapter

function captureRequests(): InternalAxiosRequestConfig[] {
  const seen: InternalAxiosRequestConfig[] = []
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    seen.push(config)
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config }
  }
  return seen
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
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
