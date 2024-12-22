import axios from 'axios'

const API_URL = 'http://elderevil.net:30008/api/v1'

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Handle token refresh here if needed
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const newTokens = await auth.refreshToken(refreshToken)
          localStorage.setItem('access_token', newTokens.access_token)
          localStorage.setItem('refresh_token', newTokens.refresh_token)

          // Retry the original request
          const config = error.config
          config.headers.Authorization = `Bearer ${newTokens.access_token}`
          return axios(config)
        } catch (refreshError) {
          // If refresh fails, logout user
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/'
          return Promise.reject(refreshError)
        }
      }
    }
    return Promise.reject(error)
  }
)

// Add request interceptor for authentication
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginCredentials {
  username: string
  password: string
}

export const auth = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    try {
      const formData = new URLSearchParams()
      formData.append('username', credentials.username)
      formData.append('password', credentials.password)
      formData.append('grant_type', 'password')
      formData.append('client_id', 'string')
      formData.append('client_secret', 'string')
      formData.append('scope', '')

      const response = await axios.post<LoginResponse>(`${API_URL}/login/access-token`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      })
      return response.data
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(error.response?.data?.detail || 'Login failed')
      }
      throw error
    }
  },

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    try {
      const formData = new URLSearchParams()
      formData.append('grant_type', 'refresh_token')
      formData.append('refresh_token', refreshToken)

      const response = await axios.post<LoginResponse>(`${API_URL}/login/refresh-token`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      })
      return response.data
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(error.response?.data?.detail || 'Token refresh failed')
      }
      throw error
    }
  }
}

export default apiClient
