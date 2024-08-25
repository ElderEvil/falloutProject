import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

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
    const originalRequest = error.config

    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      await authStore.refreshAccessToken()
      axios.defaults.headers.common['Authorization'] = 'Bearer ' + authStore.token
      return apiClient(originalRequest)
    }

    return Promise.reject(error)
  }
)

export default apiClient
