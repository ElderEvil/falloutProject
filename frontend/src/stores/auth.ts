import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

interface User {
  id: number;
  username: string;
  email: string;
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: null as string | null,
    user: null as User | null
  }),
  getters: {
    isAuthenticated: (state) => !!state.token
  },
  actions: {
    async login(username: string, password: string) {
      try {
        const response = await axios.post('/api/v1/login/access-token', {
          username: username,
          password: password
        })
        this.token = response.data.access_token
        await this.fetchUser()
        return true
      } catch (error) {
        console.error('Login failed', error)
        return false
      }
    },
    async register(username: string, email: string, password: string) {
      try {
        const response = await axios.post('/api/v1/users/open/', {
          username: username,
          email: email,
          password: password
        })
        this.token = response.data.access_token
        await this.fetchUser()
        return true
      } catch (error) {
        console.error('Registration failed', error)
        return false
      }
    },
    async fetchUser() {
      try {
        const response = await axios.get('/api/v1/users/me')
        this.user = response.data
      } catch (error) {
        console.error('Failed to fetch user', error)
      }
    },
    logout() {
      this.token = null
      this.user = null
    }
  }
})
