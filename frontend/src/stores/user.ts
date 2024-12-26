import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserState, AuthForm, UserPreferences } from '@/types/auth'
import { validateLoginForm, validateRegistrationForm } from '@/utils/authUtils'

export const useUserStore = defineStore('user', () => {
  const user = ref<UserState>({
    email: '',
    username: '',
    isAuthenticated: false,
    preferences: {
      theme: 'default'
    }
  })

  async function login(form: AuthForm): Promise<{ success: boolean; message?: string }> {
    try {
      const validation = validateLoginForm(form)
      if (!validation.isValid) {
        return { success: false, message: validation.message }
      }

      if (form.email && form.password) {
        user.value = {
          email: form.email,
          username: form.email.split('@')[0],
          isAuthenticated: true,
          preferences: {
            theme: 'default'
          }
        }
        return { success: true }
      }

      return { success: false, message: 'Invalid credentials' }
    } catch (error) {
      console.error('Login error:', error)
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Login failed'
      }
    }
  }

  async function signup(form: AuthForm): Promise<{ success: boolean; message?: string }> {
    try {
      const validation = validateRegistrationForm(form)
      if (!validation.isValid) {
        return { success: false, message: validation.message }
      }

      user.value = {
        email: form.email,
        username: form.username || form.email.split('@')[0],
        isAuthenticated: true,
        preferences: {
          theme: 'default'
        }
      }
      return { success: true }
    } catch (error) {
      console.error('Registration error:', error)
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Registration failed'
      }
    }
  }

  function updatePreferences(preferences: Partial<UserPreferences>) {
    if (user.value.preferences) {
      user.value.preferences = { ...user.value.preferences, ...preferences }
    } else {
      user.value.preferences = { theme: 'default', ...preferences }
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')

    user.value = {
      email: '',
      username: '',
      isAuthenticated: false,
      preferences: {
        theme: 'default'
      }
    }
  }

  function init() {
    const token = localStorage.getItem('access_token')
    if (token) {
      const email = localStorage.getItem('user_email')
      user.value = {
        email: email || '',
        username: email ? email.split('@')[0] : '',
        isAuthenticated: true,
        preferences: {
          theme: 'default'
        }
      }
    }
  }

  init()

  return {
    user,
    login,
    signup,
    logout
  }
})
