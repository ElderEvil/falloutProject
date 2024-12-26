import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json'
  }
})

// Type for requests that can be retried
interface RetryableRequest extends InternalAxiosRequestConfig {
  _retry?: boolean
}

apiClient.interceptors.request.use(
  async (config: RetryableRequest) => {
    const isAuthEndpoint = ['/api/v1/login/access-token', '/api/v1/login/refresh-token'].includes(
      config.url || ''
    )

    if (!isAuthEndpoint) {
      const authStore = useAuthStore()
      if (authStore.token) {
        config.headers.Authorization = `Bearer ${authStore.token}`
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const authStore = useAuthStore()

    if (!error.config) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as RetryableRequest

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      originalRequest.url !== '/api/v1/login/refresh-token'
    ) {
      try {
        originalRequest._retry = true
        await authStore.refreshAccessToken()

        if (authStore.token) {
          originalRequest.headers.Authorization = `Bearer ${authStore.token}`
          return apiClient(originalRequest)
        }
      } catch (refreshError) {
        await authStore.logout()
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
