import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') as string | null,
    refreshToken: localStorage.getItem('refreshToken') as string | null,
    user: JSON.parse(localStorage.getItem('user') as string) as User | null
  }),
  getters: {
    isAuthenticated: (state) => !!state.token
  },
  actions: {
    async login(username: string, password: string) {
      try {
        const formData = new URLSearchParams()
        formData.append('username', username)
        formData.append('password', password)

        const response = await axios.post('/api/v1/login/access-token', formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        })

        this.token = response.data.access_token
        this.refreshToken = response.data.refresh_token
        if (!this.token || !this.refreshToken) return false

        localStorage.setItem('token', this.token!)
        localStorage.setItem('refreshToken', this.refreshToken)

        await this.fetchUser()
        return true
      } catch (error) {
        console.error('Login failed', error)
        return false
      }
    },
    async register(username: string, email: string, password: string) {
      try {
        const response = await axios.post('/api/v1/users/open', {
          username: username,
          email: email,
          password: password
        })

        this.token = response.data.access_token
        this.refreshToken = response.data.refresh_token
        if (!this.token || !this.refreshToken) return false

        localStorage.setItem('token', this.token!)
        localStorage.setItem('refreshToken', this.refreshToken)

        await this.fetchUser()
        return true
      } catch (error) {
        console.error('Registration failed', error)
        return false
      }
    },
    async fetchUser() {
      if (!this.token) return

      try {
        const response = await axios.get('/api/v1/users/me', {
          headers: {
            Authorization: `Bearer ${this.token}`
          }
        })
        this.user = response.data
        localStorage.setItem('user', JSON.stringify(this.user))
      } catch (error) {
        console.error('Failed to fetch user', error)
        await this.logout()
      }
    },
    async refreshAccessToken() {
      if (!this.refreshToken) return

      try {
        const formData = new URLSearchParams()
        formData.append('refresh_token', this.refreshToken)

        const response = await axios.post('/api/v1/login/refresh-token', formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        })

        this.token = response.data.access_token
        localStorage.setItem('token', this.token!)
      } catch (error) {
        console.error('Failed to refresh token', error)
        await this.logout()
      }
    },
    async logout() {
      try {
        await axios.post(
          '/api/v1/logout',
          {},
          {
            headers: {
              Authorization: `Bearer ${this.token}`
            }
          }
        )
      } catch (error) {
        console.error('Logout failed', error)
      } finally {
        this.token = null
        this.refreshToken = null
        this.user = null
        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        localStorage.removeItem('user')
      }
    }
  }
})
