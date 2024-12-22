import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { UserState, AuthForm } from '../model/types';
import { validateLoginForm, validateSignupForm } from '../utils/validation';
import { authApi } from '../api/auth';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserState>({
    email: '',
    username: '',
    isAuthenticated: false,
    preferences: {
      theme: 'default'
    }
  });

  async function login(form: AuthForm): Promise<{ success: boolean; message?: string }> {
    try {
      const validation = validateLoginForm(form);
      if (!validation.isValid) {
        return { success: false, message: validation.message };
      }

      const response = await authApi.login({
        username: form.email,
        password: form.password
      });

      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);

      user.value = {
        email: form.email,
        username: form.email.split('@')[0],
        isAuthenticated: true,
        preferences: {
          theme: 'default'
        }
      };

      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Login failed'
      };
    }
  }

  async function signup(form: AuthForm): Promise<{ success: boolean; message?: string }> {
    try {
      const validation = validateSignupForm(form);
      if (!validation.isValid) {
        return { success: false, message: validation.message };
      }

      user.value = {
        email: form.email,
        username: form.username || form.email.split('@')[0],
        isAuthenticated: true,
        preferences: {
          theme: 'default'
        }
      };
      return { success: true };
    } catch (error) {
      console.error('Signup error:', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Signup failed'
      };
    }
  }

  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');

    user.value = {
      email: '',
      username: '',
      isAuthenticated: false,
      preferences: {
        theme: 'default'
      }
    };
  }

  function init() {
    const token = localStorage.getItem('access_token');
    if (token) {
      const email = localStorage.getItem('user_email');
      user.value = {
        email: email || '',
        username: email ? email.split('@')[0] : '',
        isAuthenticated: true,
        preferences: {
          theme: 'default'
        }
      };
    }
  }

  init();

  return {
    user,
    login,
    signup,
    logout
  };
});
