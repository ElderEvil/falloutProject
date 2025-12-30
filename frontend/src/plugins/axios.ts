import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use(
  async (config) => {
    const authStore = useAuthStore()

    if (authStore.token) {
      // Optional: Check if the token is expiring soon
      config.headers.Authorization = `Bearer ${authStore.token}`
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
  async (error) => {
    const authStore = useAuthStore()
    const notificationStore = useNotificationStore()
    const originalRequest = error.config

    // Handle 401 with token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      await authStore.refreshAccessToken()
      axios.defaults.headers.common['Authorization'] = 'Bearer ' + authStore.token
      return apiClient(originalRequest)
    }

    // Skip notifications for specific endpoints or if explicitly disabled
    if (!originalRequest._skipErrorNotification) {
      const errorData = error.response?.data
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
        } else if (status >= 500) {
          title = 'Server Error'
          message = 'Something went wrong on our end'
        }

        // Extract message from response body
        if (typeof errorData === 'string') {
          message = errorData
        } else if (errorData?.detail) {
          if (typeof errorData.detail === 'string') {
            message = errorData.detail
          } else if (Array.isArray(errorData.detail)) {
            // FastAPI validation errors
            message = errorData.detail.map((err: any) => {
              const field = err.loc?.join('.') || 'field'
              return `${field}: ${err.msg}`
            }).join(', ')
          } else if (typeof errorData.detail === 'object') {
            message = JSON.stringify(errorData.detail)
          }
        } else if (errorData?.message) {
          message = errorData.message
        }

        // Add technical details
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

      notificationStore.error(title, message, details)
    }

    return Promise.reject(error)
  }
)

export default apiClient
