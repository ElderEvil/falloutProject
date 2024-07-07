import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface User {
  id: number;
  username: string;
  email: string;
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') as string | null,
    user: null as User | null
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
        if (!this.token) return
        localStorage.setItem('token', this.token)
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
        if (!this.token) return
        localStorage.setItem('token', this.token)

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
      } catch (error) {
        console.error('Failed to fetch user', error)
        this.logout()
      }
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
    }
  }
})
