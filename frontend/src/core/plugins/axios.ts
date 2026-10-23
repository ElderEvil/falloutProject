import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useToast } from '@/core/composables/useToast'
import { claimErrorNotification } from '@/core/utils/errorNotifications'
import {
  ensureAccessToken,
  expireSession,
  getStoredToken,
  refreshSession,
} from '@/core/utils/authSession'

declare module 'axios' {
  interface AxiosRequestConfig {
    _retry?: boolean
    _skipErrorNotification?: boolean
  }
}

type CustomAxiosRequestConfig = InternalAxiosRequestConfig

interface ValidationError {
  loc: string[]
  msg: string
  type: string
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use(
  async (config) => {
    const token = config.url?.includes('/auth/') ? getStoredToken() : await ensureAccessToken()

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  async (err: unknown) => {
    // Type guard to check if error is an AxiosError
    if (!axios.isAxiosError(err)) {
      return Promise.reject(err)
    }

    const error = err as AxiosError
    const originalRequest = error.config as CustomAxiosRequestConfig | undefined

    if (!originalRequest) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401) {
      if (originalRequest._retry) {
        claimErrorNotification(error)
        expireSession()
        return Promise.reject(error)
      }
      originalRequest._retry = true
      const currentToken = getStoredToken()
      // Another request may already have refreshed while this one was in flight.
      const token =
        currentToken && originalRequest.headers.Authorization !== `Bearer ${currentToken}`
          ? currentToken
          : (await refreshSession()).data.access_token
      originalRequest.headers.Authorization = `Bearer ${token}`
      return apiClient(originalRequest)
    }

    // Skip notifications for specific endpoints or if explicitly disabled
    if (!originalRequest._skipErrorNotification) {
      const errorData = error.response?.data as Record<string, unknown> | string | undefined
      let title = 'Request Failed'
      let message = 'An unexpected error occurred'
      let details: string | undefined

      // Extract error information from backend response
      if (error.response) {
        const status = error.response.status

        // Handle different status codes
        if (status === 400) {
          title = 'Invalid Request'
        } else if (status === 401) {
          title = 'Unauthorized'
          message = 'Please log in to continue'
        } else if (status === 403) {
          title = 'Access Denied'
          message = "You don't have permission to perform this action"
        } else if (status === 404) {
          title = 'Not Found'
          message = 'The requested resource was not found'
        } else if (status === 422) {
          title = 'Validation Error'
        } else if (status === 429) {
          title = 'Rate Limit Exceeded'
          message = 'Too many requests. Please slow down and try again.'

          // Parse Retry-After header if present
          const retryAfter = error.response.headers['retry-after']
          if (retryAfter) {
            const seconds = parseInt(retryAfter, 10)
            if (!isNaN(seconds) && seconds > 0) {
              message = `Too many requests. Please wait ${seconds} seconds before trying again.`
            }
          }
        } else if (status >= 500) {
          title = 'Server Error'
          message = 'Something went wrong on our end'
        }

        // Extract message from response body
        if (typeof errorData === 'string') {
          message = errorData
        } else if (errorData && typeof errorData === 'object' && 'detail' in errorData) {
          const detail = errorData.detail
          if (typeof detail === 'string') {
            message = detail
          } else if (Array.isArray(detail)) {
            // FastAPI validation errors
            message = detail
              .map((err: ValidationError) => {
                const field = err.loc?.join('.') || 'field'
                return `${field}: ${err.msg}`
              })
              .join(', ')
          } else if (typeof detail === 'object' && detail !== null) {
            message = JSON.stringify(detail)
          }
        } else if (errorData && typeof errorData === 'object' && 'message' in errorData) {
          const msg = errorData.message
          if (typeof msg === 'string') {
            message = msg
          }
        }

        // Log technical details (not shown in toast)
        const url = originalRequest.url || 'unknown'
        const method = originalRequest.method?.toUpperCase() || 'GET'
        details = `${method} ${url} - Status ${status}`
      } else if (error.request) {
        title = 'Network Error'
        message = 'Unable to reach the server. Please check your connection.'
        details = error.message
      } else {
        details = error.message
      }

      // Log technical details to console
      if (details) {
        console.error(`API Error: ${details}`, error)
      }

      // Show user-friendly toast (no technical suffix)
      if (claimErrorNotification(error)) useToast().error(`${title}: ${message}`)
    }

    return Promise.reject(error)
  }
)

export default apiClient
